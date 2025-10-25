import { create } from 'zustand'

type RobotAvgBattery = {
  type: 'robot.avg_battery'
  avg_battery: ''
  robot_count: ''
  ts: ''
}

type RobotStatusCount = {
  type : 'robot.status_count'
  warehouse_id: ''
  statuses: ''         
  total: ''         
  per_status: ''  
  ts: ''
}

type SocketMessage = RobotAvgBattery | RobotStatusCount

interface SocketState {
	avgBattery?: RobotAvgBattery
	statusCount?: RobotStatusCount
	lastUpdate?: string
	updateData: (msg: SocketMessage) => void
}

export const useSocketStore = create<SocketState>(set => ({
	avgBattery: undefined,
	statusCount: undefined,
	lastUpdate: undefined,

	updateData: msg => {
		switch (msg.type) {
			case 'robot.avg_battery':
				set({ avgBattery: msg, lastUpdate: msg.ts })
				break
			case 'robot.status_count':
				set({ statusCount: msg, lastUpdate: msg.ts })
				break
			default:
				console.warn('⚠️ Неизвестный тип сообщения:', msg)
		}
	},
}))