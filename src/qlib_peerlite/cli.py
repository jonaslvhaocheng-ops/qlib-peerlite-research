from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import pandas as pd
import typer

from .config import ExperimentConfig, load_config
from .data.schema import score_frame
from .data.synthetic import make_synthetic_dataset
from .evaluation.metrics import evaluate_predictions
from .evaluation.portfolio import backtest_weekly_top_fraction, portfolio_metrics
from .governance.artifacts import (
    append_jsonl,
    atomic_write_json,
    environment_report,
    git_identity,
    sha256_file,
)
from .models.lightgbm_model import LightGBMBaseline
from .models.mlp import MLPBaseline
from .models.peerlite import PeerLiteModel
from .production import ProductionError, authorize_shadow, load_shadow_policy, run_shadow_cycle

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _build_model(config: ExperimentConfig):
    model = config.model
    training = config.training
    common = {
        "seed": training.seed,
    }
    if model.family == "lightgbm":
        return LightGBMBaseline(**common)
    if model.family == "mlp":
        return MLPBaseline(
            model.input_dim,
            hidden_dim=model.hidden_dim,
            dropout=model.dropout,
            epochs=training.epochs,
            patience=training.patience,
            learning_rate=training.learning_rate,
            weight_decay=training.weight_decay,
            device=training.device,
            **common,
        )
    return PeerLiteModel(
        model.input_dim,
        hidden_dim=model.hidden_dim,
        num_peers=model.num_peers,
        num_heads=model.num_heads,
        dropout=model.dropout,
        market_dim=model.market_dim,
        market_gate=model.market_gate,
        loss=model.loss,
        epochs=training.epochs,
        patience=training.patience,
        learning_rate=training.learning_rate,
        weight_decay=training.weight_decay,
        gradient_clip_norm=training.gradient_clip_norm,
        device=training.device,
        **common,
    )


@app.command("validate-config")
def validate_config(config: Annotated[Path, typer.Option(exists=True, dir_okay=False)]) -> None:
    parsed = load_config(config)
    typer.echo(parsed.model_dump_json(indent=2))


@app.command("environment-report")
def write_environment_report(
    output: Annotated[Path, typer.Option(dir_okay=False)],
    project_root: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    report = environment_report(project_root)
    atomic_write_json(output, report)
    typer.echo(f"wrote {output}")


@app.command("synthetic-demo")
def synthetic_demo(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option(file_okay=False)],
) -> None:
    parsed = load_config(config)
    if parsed.track != "SYNTHETIC":
        raise typer.BadParameter("synthetic-demo only accepts track=SYNTHETIC")
    output.mkdir(parents=True, exist_ok=False)

    dataset = make_synthetic_dataset(
        n_features=parsed.model.input_dim,
        seed=parsed.training.seed,
    )
    model = _build_model(parsed)
    model.fit(dataset)
    scores = model.predict(dataset, segment="test")
    labels = dataset.prepare("test", col_set="label").iloc[:, 0]
    prediction_table = score_frame(scores.index, scores.to_numpy(), model.model_id, "synthetic")
    prediction_path = output / "predictions.parquet"
    prediction_table.to_parquet(prediction_path, index=False)

    portfolio_input = pd.concat(
        [
            scores.rename("score"),
            labels.rename("forward_return"),
        ],
        axis=1,
    )
    portfolio_input["tradable"] = True
    portfolio_input["adv20"] = 2_000_000_000.0
    portfolio_returns, holdings = backtest_weekly_top_fraction(
        portfolio_input,
        top_fraction=parsed.portfolio.top_fraction,
        max_name_weight=parsed.portfolio.max_name_weight,
        adv_participation_limit=parsed.portfolio.adv_participation_limit,
        cost_bps_per_side=parsed.portfolio.base_cost_bps_per_side,
        rebalance_weekday=parsed.portfolio.rebalance_weekday,
    )
    returns_path = output / "portfolio_returns.parquet"
    holdings_path = output / "holdings.parquet"
    portfolio_returns.reset_index().to_parquet(returns_path, index=False)
    holdings.to_parquet(holdings_path, index=False)

    metrics = evaluate_predictions(scores, labels)
    metrics.update(portfolio_metrics(portfolio_returns))
    atomic_write_json(output / "metrics.json", metrics)

    run_manifest = {
        "schema_version": "qlib_peerlite_run_manifest_v1",
        "run_id": output.name,
        "created_at": datetime.now(SHANGHAI).isoformat(),
        "track": "SYNTHETIC",
        "claim_ceiling": "MECHANICS_ONLY",
        "model_id": model.model_id,
        "config": parsed.model_dump(mode="json"),
        "git": git_identity(Path.cwd()),
        "artifacts": {
            path.name: sha256_file(path)
            for path in (
                prediction_path,
                returns_path,
                holdings_path,
                output / "metrics.json",
            )
        },
        "limitations": [
            "synthetic data cannot prove PIT eligibility",
            "synthetic performance cannot support an alpha claim",
            "no final OOS was accessed",
        ],
    }
    atomic_write_json(output / "run_manifest.json", run_manifest)
    append_jsonl(
        Path("artifacts/progress/events.jsonl"),
        {
            "timestamp": datetime.now(SHANGHAI).isoformat(),
            "phase": "M4-M7-SYNTHETIC",
            "executed": True,
            "completed": True,
            "passed": "DESIGN_ONLY",
            "run_manifest": str(output / "run_manifest.json"),
            "model_id": model.model_id,
        },
    )
    typer.echo(json.dumps(metrics, ensure_ascii=False, indent=2))


def _production_failure(error: ProductionError) -> None:
    typer.echo(json.dumps(error.as_dict(), ensure_ascii=False), file=sys.stderr)
    raise typer.Exit(code=2)


@app.command("shadow-preflight")
def shadow_preflight(
    policy: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    project_root: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path("."),
) -> None:
    try:
        parsed = load_shadow_policy(policy)
        result = authorize_shadow(parsed, project_root)
    except ProductionError as error:
        _production_failure(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@app.command("shadow-cycle")
def shadow_cycle(
    policy: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    predictions: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    source_manifest: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    state_root: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    cycle_id: Annotated[str, typer.Option()],
    as_of: Annotated[str, typer.Option()],
    project_root: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path("."),
) -> None:
    try:
        instant = datetime.fromisoformat(as_of)
        result = run_shadow_cycle(
            policy_path=policy,
            predictions_path=predictions,
            source_manifest_path=source_manifest,
            state_root=state_root,
            cycle_id=cycle_id,
            as_of=instant,
            project_root=project_root,
        )
    except ValueError:
        _production_failure(ProductionError("INVALID_AS_OF", "as_of must be ISO-8601"))
    except ProductionError as error:
        _production_failure(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))
