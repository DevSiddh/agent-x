# Template source: microsoft/qlib | Difficulty: hard | Niche: stocks
import lightgbm as lgb
import mlflow
from config import MLFLOW_URI, MODEL

def train(X_train, y_train, X_val, y_val):
    mlflow.set_tracking_uri(MLFLOW_URI)
    with mlflow.start_run():
        params = {
            "objective": "regression",
            "num_leaves": {{NUM_LEAVES}},
            "learning_rate": {{LEARNING_RATE}},
            "n_estimators": {{N_ESTIMATORS}},
            # {{ADD_HYPERPARAMS}}
        }
        model = lgb.LGBMRegressor(**params)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
                  callbacks=[lgb.early_stopping(50)])
        mlflow.log_params(params)
        mlflow.lightgbm.log_model(model, "model")
    return model

def predict(model, X) -> list:
    return model.predict(X)
