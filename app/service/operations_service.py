from typing import List
from app.repositories.operations_repo import OperationsRepository
from app.schemas.operations import AllOperationsResponse, DeliveryShortResponse, ShipmentShortResponse
from app.models.delivery import Delivery
from app.models.shipment import Shipment


class OperationsService:
    def __init__(self, repo: OperationsRepository):
        self.repo = repo

    async def get_all_operations(self) -> AllOperationsResponse:
        """Получить все поставки и отгрузки"""
        deliveries, shipments = await self.repo.get_all_operations()
        
        # Преобразуем модели в схемы ответа
        delivery_responses = [
            DeliveryShortResponse(
                id=delivery.id,
                name=delivery.name,
                supplier=delivery.supplier,
                scheduled_at=delivery.scheduled_at,
                quantity=delivery.quantity,
                status=delivery.status,
                warehouse_id=delivery.warehouse_id
            )
            for delivery in deliveries
        ]
        
        shipment_responses = [
            ShipmentShortResponse(
                id=shipment.id,
                name=shipment.name,
                customer=shipment.customer,
                scheduled_at=shipment.scheduled_at,
                quantity=shipment.quantity,
                status=shipment.status,
                warehouse_id=shipment.warehouse_id
            )
            for shipment in shipments
        ]
        
        return AllOperationsResponse(
            deliveries=delivery_responses,
            shipments=shipment_responses
        )

    async def get_all_deliveries(self) -> List[DeliveryShortResponse]:
        """Получить только поставки"""
        deliveries = await self.repo.get_all_deliveries()
        return [
            DeliveryShortResponse(
                id=delivery.id,
                name=delivery.name,
                supplier=delivery.supplier,
                scheduled_at=delivery.scheduled_at,
                quantity=delivery.quantity,
                status=delivery.status,
                warehouse_id=delivery.warehouse_id
            )
            for delivery in deliveries
        ]

    async def get_all_shipments(self) -> List[ShipmentShortResponse]:
        """Получить только отгрузки"""
        shipments = await self.repo.get_all_shipments()
        return [
            ShipmentShortResponse(
                id=shipment.id,
                name=shipment.name,
                customer=shipment.customer,
                scheduled_at=shipment.scheduled_at,
                quantity=shipment.quantity,
                status=shipment.status,
                warehouse_id=shipment.warehouse_id
            )
            for shipment in shipments
        ]