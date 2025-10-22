from app.models.user import User
from app.models.robot import Robot
from app.models.product import Product
from app.models.inventory_history import InventoryHistory
from app.models.ai_prediction import AIPrediction
from app.models.keycloak_user import KeycloakUser

# Список всех моделей для импорта
__all__ = ["Base", "User", "Product", "Robot", "Inventory_History", "Ai_Prediction", "kkid_userid", "KeycloakUser"]