from pathlib import Path
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Project-relative paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "07_AI_ML" / "data" / "recovery_training.csv"
MODEL_DIR = PROJECT_ROOT / "07_AI_ML" / "models"
MODEL_PATH = MODEL_DIR / "recovery_model.pkl"


def train():
    # 1. Load recovery_training.csv
    print(f"Loading training data from: {DATA_PATH.relative_to(PROJECT_ROOT)}")
    df = pd.read_csv(DATA_PATH)

    # 2. Separate features and target (will_recover)
    target_column = "will_recover"
    X = df.drop(columns=[target_column])
    y = df[target_column]

    # 3. Preprocess numerical and categorical features
    numerical_features = [
        "amount",
        "customer_success_rate",
        "previous_retries",
        "retry_success_rate",
        "time_since_failure",
    ]
    categorical_features = [
        "failure_reason",
        "payment_method",
        "recovery_action",
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numerical_features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ]
    )

    # 4. Split into train/test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 5. Build and train complete pipeline with Logistic Regression
    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(random_state=42)),
        ]
    )

    print("Training Logistic Regression pipeline...")
    pipeline.fit(X_train, y_train)

    # 6. Evaluate and report metrics
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    print("\n--- Model Evaluation ---")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1 Score:  {f1:.4f}")

    # 7. Save the complete trained pipeline
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"\nModel pipeline saved successfully to: {MODEL_PATH.relative_to(PROJECT_ROOT)}")

    return pipeline


if __name__ == "__main__":
    train()
