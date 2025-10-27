import { create } from 'zustand'

type RobotAvgBattery = {
  type: 'robot.avg_battery'
	warehouse_id: string
  avg_battery: number
}

type RobotActiveRobots = {
	type: 'robot.active_robots'
	warehouse_id: string
	active_robots: number
	robots: number
}

type InventoryCriticalUnique = {
  type: 'inventory.critical_unique'
	warehouse_id: string
  unique_articles: number
}

type InventoryScanned24h = {
	type: 'inventory.scanned_24h'
	warehouse_id: string
	count: number
}

type InventoryStatusAvg = {
  type: 'inventory.status_avg'
  warehouse_id: string
	status: string
	max_avg: number
}

type RobotActivitySeries = {
	type: 'robot.activity_series'
	warehouse_id: string
	window_min: number
	bucket_sec: number
	series: [string,number][]
	ts: string
	total_robots: number
}

type Product = {
	id: string
	name: string
	article: string
	stock: string
	status: string
	zone: string
	scanned_at: string
}


type ProductScan = {
	type: 'product.scan'
	warehouse_id: string
	robot_id: string
	products: Product[]
}



type SocketMessage =
	| RobotAvgBattery
	| RobotActiveRobots
	| InventoryScanned24h
	| InventoryCriticalUnique
	| InventoryStatusAvg
	| RobotActivitySeries
	| ProductScan

interface SocketState {
	avgBattery?: RobotAvgBattery
	robotsData?: RobotActiveRobots
	scanned24h?: InventoryScanned24h
	criticalUnique?: InventoryCriticalUnique
	statusAvg?: InventoryStatusAvg
	activitySeries?: RobotActivitySeries
	productScan?: ProductScan
	updateData: (msg: SocketMessage) => void
}

export const useSocketStore = create<SocketState>(set => ({
	avgBattery: undefined,
	statusCount: undefined,
	scanned24h: undefined,
	criticalUnique: undefined,
	statusAvg: undefined,
	activitySeries: undefined,
	productScan: undefined,
	lastUpdate: undefined,

	updateData: msg => {
		switch (msg.type) {
			case 'robot.avg_battery':
				set({ avgBattery: msg })
				break
			case 'robot.active_robots':
				set({ robotsData: msg })
				break
			case 'inventory.scanned_24h':
				set({ scanned24h: msg })
				break
			case 'inventory.critical_unique':
				set({ criticalUnique: msg })
				break
			case 'inventory.status_avg':
				set({ statusAvg: msg })
				break
			case 'robot.activity_series':
				set(state => ({
					activitySeries: {
						...msg,
						series: [
							...(state.activitySeries?.series || []),
							...msg.series,
						].slice(-60),
					},
				}))
				break
			case 'product.scan':
				set({ productScan: msg })
				break
			default:
				console.warn('⚠️ Неизвестный тип сообщения:', msg)
		}
	},
}))