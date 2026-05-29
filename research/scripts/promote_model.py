"""
Model Promotion Script
Moves models from candidates to production after review and validation
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


class ModelPromoter:
    """Handles promotion of models from candidates to production."""

    def __init__(self, models_dir: str = "../../models"):
        self.models_dir = Path(models_dir).resolve()
        self.candidates_dir = self.models_dir / "candidates"
        self.production_dir = self.models_dir / "production"
        self.archive_dir = self.models_dir / "archive"

        # Ensure directories exist
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.production_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def list_candidates(self):
        """List all candidate models."""
        candidates = []
        for model_dir in self.candidates_dir.iterdir():
            if model_dir.is_dir():
                metadata_path = model_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                        metadata["model_id"] = model_dir.name
                        candidates.append(metadata)
        return candidates

    def list_production(self):
        """List all production models."""
        production = []
        for model_dir in self.production_dir.iterdir():
            if model_dir.is_dir():
                metadata_path = model_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                        metadata["model_id"] = model_dir.name
                        production.append(metadata)
        return production

    def validate_model(self, model_id: str):
        """Validate a candidate model before promotion."""
        model_dir = self.candidates_dir / model_id

        if not model_dir.exists():
            return False, f"Model {model_id} not found in candidates"

            # Check required files
        required_files = ["model.pkl", "metadata.json"]
        for file_name in required_files:
            if not (model_dir / file_name).exists():
                return False, f"Missing required file: {file_name}"

                # Load and validate metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

            # Check required metadata fields
        required_fields = ["model_type", "created_at", "feature_columns"]
        for field in required_fields:
            if field not in metadata:
                return False, f"Missing required metadata field: {field}"

                # Validate performance metrics
        if "sharpe_ratio" in metadata:
            sharpe = metadata["sharpe_ratio"]
            if sharpe < 0:
                return False, f"Sharpe ratio is negative: {sharpe}"

        return True, "Model validation passed"

    def promote_model(self, model_id: str, force: bool = False):
        """Promote a candidate model to production."""
        # Validate model
        if not force:
            is_valid, message = self.validate_model(model_id)
            if not is_valid:
                print(f"❌ Validation failed: {message}")
                return False
            print(f"✓ Validation passed: {message}")

        source_dir = self.candidates_dir / model_id
        dest_dir = self.production_dir / model_id

        # Check if model already exists in production
        if dest_dir.exists():
            print(f"⚠️  Model {model_id} already exists in production")
            response = input("Archive existing version? (y/n): ")
            if response.lower() == "y":
                self.archive_model(model_id)
            else:
                print("Promotion cancelled")
                return False

                # Copy model to production
        try:
            shutil.copytree(source_dir, dest_dir)

            # Update metadata
            metadata_path = dest_dir / "metadata.json"
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            metadata["promoted_at"] = datetime.now().isoformat()
            metadata["status"] = "production"

            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            print(f"✓ Model {model_id} promoted to production successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to promote model: {e}")
            return False

    def archive_model(self, model_id: str, from_production: bool = True):
        """Archive a model from production."""
        source_dir = (
            self.production_dir / model_id
            if from_production
            else self.candidates_dir / model_id
        )

        if not source_dir.exists():
            print(f"❌ Model {model_id} not found")
            return False

            # Create archive directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dest = self.archive_dir / f"{model_id}_{timestamp}"

        try:
            shutil.move(str(source_dir), str(archive_dest))
            print(f"✓ Model {model_id} archived to {archive_dest}")
            return True
        except Exception as e:
            print(f"❌ Failed to archive model: {e}")
            return False

    def rollback_model(self, model_id: str):
        """Rollback a production model to most recent archived version."""
        archives = list(self.archive_dir.glob(f"{model_id}_*"))
        if not archives:
            print(f"❌ No archived versions found for {model_id}")
            return False

        latest_archive = max(archives, key=lambda p: p.stat().st_mtime)
        dest_dir = self.production_dir / model_id

        try:
            if dest_dir.exists():
                shutil.rmtree(dest_dir)

            shutil.copytree(latest_archive, dest_dir)
            print(f"✓ Model {model_id} rolled back from {latest_archive}")
            return True

        except Exception as e:
            print(f"❌ Failed to rollback model: {e}")
            return False


def main():
<<<<<<< HEAD
    parser = argparse.ArgumentParser(description="Manage model promotion lifecycle")
=======
    parser = argparse.ArgumentParser(
        description="Manage model promotion lifecycle")
>>>>>>> refactor/service-cleanup
    parser.add_argument(
        "command", choices=["list", "promote", "archive", "rollback", "validate"]
    )
    parser.add_argument("--model-id", help="Model identifier")
    parser.add_argument("--force", action="store_true", help="Skip validation")
    parser.add_argument(
        "--models-dir", default="../../models", help="Base models directory"
    )
    args = parser.parse_args()

    promoter = ModelPromoter(args.models_dir)

    if args.command == "list":
        print("\n=== Candidate Models ===")
        candidates = promoter.list_candidates()
        for model in candidates:
            print(
                f"  {model['model_id']}: {model.get('model_type', 'Unknown')} "
                f"(Sharpe: {model.get('sharpe_ratio', 'N/A')})"
            )

        print("\n=== Production Models ===")
        production = promoter.list_production()
        for model in production:
            print(
                f"  {model['model_id']}: {model.get('model_type', 'Unknown')} "
                f"(Promoted: {model.get('promoted_at', 'Unknown')})"
            )

    elif args.command == "promote":
        if not args.model_id:
            print("❌ --model-id required for promote command")
            return
        promoter.promote_model(args.model_id, force=args.force)

    elif args.command == "archive":
        if not args.model_id:
            print("❌ --model-id required for archive command")
            return
        promoter.archive_model(args.model_id)

    elif args.command == "rollback":
        if not args.model_id:
            print("❌ --model-id required for rollback command")
            return
        promoter.rollback_model(args.model_id)

    elif args.command == "validate":
        if not args.model_id:
            print("❌ --model-id required for validate command")
            return
        is_valid, message = promoter.validate_model(args.model_id)
        if is_valid:
            print(f"✓ {message}")
        else:
            print(f"❌ {message}")


if __name__ == "__main__":
    main()
