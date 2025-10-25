import { create } from 'zustand'
import axios from 'axios'

export type Warehouse = {
	id: string
	name: string
	address: string
	products_count: number
	max_products: number
}

type WarehouseStore = {
	warehouses: Warehouse[]
	loading: boolean
	error: string | null
	selectedWarehouse: Warehouse | null
	fetchWarehouses: (token: string) => Promise<void>
	setSelectedWarehouse: (wh: Warehouse | null) => void
	updateWarehouse: (warehouse: Warehouse) => void
}

export const useWarehouseStore = create<WarehouseStore>((set, get) => ({
	warehouses: [],
	loading: false,
	error: null,
	selectedWarehouse: null,

	fetchWarehouses: async (token: string) => {
		set({ loading: true, error: null })
		try {
			const res = await axios.get(
				'https://rtk-smart-warehouse.ru/api/v1/warehouses',
				{
					headers: { Authorization: `Bearer ${token}` },
				}
			)
			set({ warehouses: res.data, loading: false })
		} catch (err) {
			set({ error: 'Не удалось получить список складов', loading: false })
		}
	},

	setSelectedWarehouse: wh => set({ selectedWarehouse: wh }),

	updateWarehouse: updated => {
		set({
			warehouses: get().warehouses.map(w =>
				w.id === updated.id ? updated : w
			),
			selectedWarehouse: updated,
		})
	},
}))
