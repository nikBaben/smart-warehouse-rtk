import api from '@/api/axios'
import { useEffect, useState } from 'react'
import { useUserStore } from '@/store/useUserStore.tsx'
import { useWarehouseStore } from '@/store/useWarehouseStore.tsx'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import type { Warehouse } from '../types/warehouse.ts'
import AddSmall from '@atomaro/icons/24/action/AddSmall'
import { UserAvatar } from '../ui/UserAvatar.tsx'
import { AddWarehouseDialog } from '../ui/AddWarehouseDialog.tsx'
import { Check } from 'lucide-react'
import { toast } from 'sonner'
import { WarehouseList } from '../warehouses/WarehousesList.tsx'
import { Skeleton } from '@/components/ui/skeleton'
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '@/components/ui/select'
import { X } from 'lucide-react'
import {
	Dialog,
	DialogClose,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from '@/components/ui/dialog'

type WhRobot = {
	status: string
	id: string
	battery_level: number
}

type WhProduct = {
	id: string
	name: string
	article: string
	category: string
	stock: number
	current_row: number
	current_shelf: string
	current_position: string
	status: string
}

function SuppliesPage() {
	
	return (
		<div className='flex bg-[#F4F4F5] min-h-screen'>
			<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
				<header className='header-style'>
					<span className='pagename-font'>Поставки</span>
					<div className='flex items-center space-x-5'>
						{/* <AddWarehouseDialog /> */}
						<UserAvatar />
					</div>
				</header>

				<main className='flex-1 p-3 h-full'>
					<div className='grid grid-cols-12 gap-3 justify-between h-full'>
						<section className='bg-white rounded-[15px] col-span-6 h-full p-[10px]'>
							<h2 className='big-section-font mb-3'>Поступления</h2>
						</section>

						<section className='bg-white rounded-[15px] col-span-6 h-full p-[10px] space-y-5'>
							<h2 className='big-section-font'>Отгрузки</h2>
						</section>
					</div>
				</main>
			</div>
		</div>
	)
}

export default SuppliesPage
