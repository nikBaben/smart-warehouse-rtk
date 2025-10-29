import { useEffect, useState} from "react";
import { ScanStoryTable } from "../widgets/ScanStoryTable.tsx";
import { RobotActivityChart } from "@/components/widgets/RobotActivityChart";
import { Button } from "@/components/ui/button";
import AddLarge from '@atomaro/icons/24/action/AddLarge';
import { ForecastAI } from "../widgets/ForecastAI";
import { UserAvatar } from '../ui/UserAvatar.tsx'
import { AddRobotProductDialog } from '../ui/AddRobotProductDialog.tsx'
import { Spinner } from '@/components/ui/spinner'
import { useWarehouseSocket } from '@/hooks/useWarehouseSocket.tsx'
import { useSocketStore } from '@/store/useSocketStore.tsx'
import { useWarehouseStore } from '@/store/useWarehouseStore.tsx'

import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '@/components/ui/select'

function DashboardPage(){
	const token = localStorage.getItem('token')
	const { warehouses, selectedWarehouse, setSelectedWarehouse, loading, error } = useWarehouseStore()
	const { avgBattery, robotsData, scanned24h, criticalUnique, statusAvg } = useSocketStore()
	const { readyState } = useWarehouseSocket(selectedWarehouse?.id ?? '')
	
	const getStatusName = (status: string) => {
		switch (status) {
			case 'ok':
				return 'ОК'
			case 'low':
				return 'низкий остаток'
			case 'critical':
				return 'критично'
			default:
				return 'неизвестен'
		}
	}

	const { fetchWarehouses } = useWarehouseStore()
/* 	useEffect(()=>{
		if (token) fetchWarehouses(token)
	},[token]) */
	useEffect(() => {
		fetchWarehouses()
	}, [])
  return (
		<div className='flex bg-[#F4F4F5] min-h-screen'>
			<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
				<header className='bg-white justify-between flex items-center h-[60px] px-[14px] z-10'>
					<span className='pagename-font'>Дашборд</span>
					<div className='ml-auto flex items-center gap-4'>
						<div className='relative'>
							<Select
								value={selectedWarehouse?.id || ''}
								onValueChange={id => {
									const wh = warehouses.find(w => w.id === id) || null
									setSelectedWarehouse(wh)
								}}
							>
								<SelectTrigger className='select-warehouse'>
									<SelectValue placeholder='Выберите склад' />
								</SelectTrigger>
								<SelectContent>
									{loading ? (
										<div className='spinner-load-container'>
											<Spinner className='size-5 m-1' /> загрузка складов...
										</div>
									) : error ? (
										<div className='flex items-center justify-center text-[20px] text-[#FF9393]'>
											не удалось загрузить
										</div>
									) : warehouses.length === 0 ? (
										<div className='flex items-center justify-center text-[20px] text-[#FED388]'>
											нет доступных складов
										</div>
									) : (
										warehouses.map(w => (
											<SelectItem key={w.id} value={w.id.toString()}>
												{w.name}
											</SelectItem>
										))
									)}
								</SelectContent>
							</Select>
						</div>
						<div className='flex items-center space-x-5'>
							{selectedWarehouse?.id ? <AddRobotProductDialog /> : <></>}
							<UserAvatar />
						</div>
					</div>
				</header>
				<main className='flex-1 overflow-auto p-[10px]'>
					{selectedWarehouse?.id == null ? (
						<div className='flex items-center justify-center font-medium text-center h-full text-[#9699A3] text-[40px]'>
							<h1>выберите склад для отображения дашборда</h1>
						</div>
					) : (
						<div className='grid grid-cols-12 gap-3 h-full'>
							<section className='bg-white rounded-[10px] p-[6px] pl-[12px] flex flex-col col-span-5'>
								<h2 className='font-semibold text-[18px] mb-3'>Карта склада</h2>
								<div className='flex-1 bg-[#F6F7F7] rounded-[10px]'></div>
							</section>
							<section className='col-span-7 gap-4 auto-rows-min space-y-[10px]'>
								<div className='bg-transparent grid grid-cols-7 gap-3 col-span-2 w-full'>
									{criticalUnique?.unique_articles ? (
										<div className='spinner-load-container'>
											<Spinner className='size-5 m-1' /> загружаем критические
											остатки...
										</div>
									) : (
										<div className='dashboard-card'>
											<h3 className='font-medium text-[18px] mb-1'>
												Критические остатки
											</h3>
											<div className='flex flex-col items-center justify-between space-y-[-8px] pb-4'>
												<p className='text-[28px] font-bold'>
													{criticalUnique?.unique_articles}
												</p>
												<p className='text-[10px] text-[#CCCCCC] font-light'>
													{' '}
													количество SKU{' '}
												</p>
											</div>
										</div>
									)}
									<div className='dashboard-card'>
										<h3 className='font-medium text-[18px] mb-1'>
											Проверено за 24ч
										</h3>
										<div className='flex flex-col items-center justify-between space-y-[-8px] pb-4'>
											<p className='text-[28px] font-bold'>
												{scanned24h?.count}
											</p>
											<p className='text-[10px] text-[#CCCCCC] font-light'>
												{' '}
												позиций{' '}
											</p>
										</div>
									</div>
									<div className='dashboard-card !col-span-3'>
										{statusAvg?.status === '' ? (
											<div className='spinner-load-container'>
												<Spinner className='size-4 m-1' /> определяем ср. статус склада...
											</div>
										) : (
											<div>
												<h3 className='font-medium text-[18px] mb-1'>
													Ср. статус по складу
												</h3>
												<div className='flex flex-col items-center justify-between space-y-[-8px] pb-4'>
													<p className='text-[28px] font-bold'>
														{getStatusName(statusAvg?.status || '')}
													</p>
													<p className='text-[10px] text-[#CCCCCC] font-light'>
														{' '}
														статистика{' '}
													</p>
												</div>
											</div>
										)}
									</div>
								</div>
								<div className='bg-transparent grid grid-cols-7 gap-3 col-span-2 w-full h-[200px]'>
									<div className='bg-white rounded-[10px] pt-[6px] pl-[10px] pr-[10px] pb-[10px] col-span-5'>
										<h3 className='font-medium text-[18px] mb-1'>
											График активности роботов
										</h3>
										<div className='h-[150px] bg-white rounded-[10px] flex items-center justify-center'>
											<RobotActivityChart />
										</div>
									</div>
									<div className='flex flex-col col-span-2 gap-3'>
										<div className='dashboard-card !h-full'>
											{robotsData?.robots ? (
												<div>
													<h3 className='font-medium text-[18px]'>Роботы</h3>
													<div className='flex flex-col items-center justify-center space-y-[-8px]'>
														<span className='text-[30px] font-bold'>
															{robotsData?.active_robots}/{robotsData?.robots}
														</span>
														<p className='text-[10px] text-[#CCCCCC] font-light'>
															активных/всего
														</p>
													</div>
												</div>
											) : (
												<div className='spinner-load-container'>
													<Spinner className='size-4 m-1' /> загружаем
													роботов...
												</div>
											)}
										</div>
										<div className='dashboard-card !h-full'>
											<h3 className='font-medium text-[18px]'>
												Ср. заряд батарей
											</h3>
											<div className='flex flex-col items-center justify-center space-y-[-8px]'>
												<span className='text-[30px] font-bold'>
													{avgBattery?.avg_battery.toFixed(2)}%
												</span>
												<p className='text-[10px] text-[#CCCCCC] font-light'>
													среднее значение
												</p>
											</div>
										</div>
									</div>
								</div>
								<div className='bg-white rounded-[10px] pl-[10px] pt-[6px] pr-[10px] pb-[10px] col-span-2 h-[334px]'>
									<h3 className='font-medium text-[18px]'>
										Последние сканирования
									</h3>
									<ScanStoryTable />
								</div>
								<div className='bg-white rounded-[10px] pl-[10px] pt-[6px] pr-[10px] pb-[10px] col-span-2'>
									<ForecastAI />
								</div>
							</section>
						</div>
					)}
				</main>
			</div>
		</div>
	)
};

export default DashboardPage;
