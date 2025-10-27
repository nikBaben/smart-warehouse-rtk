import { useEffect } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'
import { useSocketStore } from '.././store/useSocketStore'

export function useWarehouseSocket(warehouseId:string){
  const { updateData } = useSocketStore()
  
  const { lastMessage, readyState } = useWebSocket(
		`wss://dev.rtk-smart-warehouse.ru/api/ws/warehouses/${warehouseId}`,
		{
			shouldReconnect: () => true,
			reconnectAttempts: Infinity,
			reconnectInterval: 3000,
		}
	)
  useEffect(() => {
		if (!warehouseId) return
		if (lastMessage?.data) {
			try {
				const parsed = JSON.parse(lastMessage.data)
				updateData(parsed)
			} catch (err) {
				console.error('Ошибка парсинга WS:', err)
			}
		}
	}, [lastMessage, updateData])
  return { readyState }
}
