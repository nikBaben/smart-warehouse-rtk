import { useEffect } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'
import { useSocketStore } from '@/store/useSocketStore'

export function useWarehouseSocket(warehouseId?: string) {
  const updateData = useSocketStore(state => state.updateData)

  const socketUrl = warehouseId
		? `wss://dev.rtk-smart-warehouse.ru/api/ws/warehouses/${warehouseId}`
		: null

  const { lastMessage, readyState } = useWebSocket(socketUrl,{
		shouldReconnect: (closeEvent) => {
    	console.warn('WS закрыт с кодом:', closeEvent?.code)
    	return closeEvent?.code !== 1000 // 1000 = нормальное закрытие
		},
	  reconnectAttempts: Infinity,
    reconnectInterval: 3000,
	})

  useEffect(() => {
    if (!lastMessage?.data) return

    try {
      const parsed = JSON.parse(lastMessage.data)
      if (parsed?.type) {
        console.log('📩 WS message:', parsed)
        updateData(parsed)
      } else {
        console.warn('⚠️ Неизвестный формат WS сообщения:', parsed)
      }
    } catch (err) {
      console.error('Ошибка парсинга WS:', err, lastMessage.data)
    }
  }, [lastMessage, updateData])

  return { readyState }
}
