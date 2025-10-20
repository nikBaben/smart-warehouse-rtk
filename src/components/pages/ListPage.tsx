import { useEffect, useState } from 'react'
import axios from 'axios'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import AddSmall from '@atomaro/icons/24/action/AddSmall'

// 🔹 Тип данных склада (адаптирован под API)
/* type Warehouse = {
	name: string
	adress: string
	products_count: number
} */

/* type WhRobot = {
	status: string
	id: string
	battery_level: number
} */

/* type WhProduct = {
	name: string
	warehouse_id: string
	optimal_stock: number
} */

type Warehouse = {
	name: string
	adress: string
	products_count: number
	robots: {
		id: string
		status: string
		battery_level: number
		current_zone: string
	}[]
	products: {
		id: string
		name: string
		category: string
		optimal_stock: number
		min_stock: number
	}[]
}

function ListPage() {
	//-----ОБРАБОТКА СОСТОЯНИЙ-----
	const [warehouses, setWarehouses] = useState<Warehouse[]>([])
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState<string | null>(null)
	const [selectedWarehouse, setSelectedWarehouse] = useState<Warehouse | null>(
		null
	)

	//-----ЗАГРУЗКА СПИСКА СКЛАДОВ-----
	useEffect(() => {
		const fetchWarehouses = async () => {
			try {
				const response = await axios.get(
					'http://51.250.97.137:8001/api/v1/warehouse/all',
					{
						headers: { 'Content-Type': 'application/json' },
					}
				)
				console.log('Ответ сервера:', response.data)
				setWarehouses(response.data)
			} catch (err) {
				console.error('Ошибка загрузки:', err)
				setError('Не удалось загрузить склады')
			}
		}

		fetchWarehouses()
	}, [])

	const handleSelect = (warehouse: Warehouse) => {
		setSelectedWarehouse(prev =>
			prev?.name === warehouse.name ? null : warehouse
		)
	}

	return (
		<div className='flex bg-[#F4F4F5] min-h-screen'>
			<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
				<header className='bg-white h-[60px] flex items-center px-[14px] z-10'>
					<span className='pagename-font'>Список складов</span>
				</header>

				<main className='flex-1 p-3 h-full'>
					<div className='grid grid-cols-24 gap-3 justify-between h-full'>
						<section className='bg-white rounded-[15px] col-span-10 h-full p-[10px] overflow-y-auto'>
							<h2 className='big-section-font mb-3'>Список складов</h2>

							<div className='space-y-2'>
								{warehouses.map(wh => (
									<div
										key={wh.name}
										onClick={() => handleSelect(wh)}
										className={`flex justify-between items-center bg-[#F2F3F4] rounded-[15px] max-h-[60px] px-[10px] py-[10px] cursor-pointer transition-all border-[2px]
												${
													selectedWarehouse?.name === wh.name
														? 'border-[2px] border-[#7700FF] shadow-[0_0_10px_rgba(119,0,255,0.3)]'
														: 'border border-transparent hover:border-[2px] hover:border-[#7700FF33] hover:shadow-[0_0_10px_rgba(119,0,255,0.3)]'
												}`}
									>
										<div className='flex items-center'>
											<span className='text-[20px] font-medium text-black'>
												{wh.name}
											</span>
										</div>
										<div className='text-right space-y-0'>
											<div className='text-[14px] font-normal text-[#5A606D]'>
												город: {wh.adress}
											</div>
											<div className='text-[14px] font-normal text-[#5A606D]'>
												текущее количество товаров: {wh.products_count}
											</div>
										</div>
									</div>
								))}
							</div>
						</section>

						<section className='bg-white rounded-[15px] col-span-14 h-full p-[10px] space-y-5'>
							<h2 className='big-section-font'>Подробная информация о складе</h2>

							{!selectedWarehouse ? (
								<div className='flex items-center justify-center font-medium h-full text-[#9699A3] text-[24px]'>
									выберите склад для отображения подробной информации
								</div>
							) : (
								<>
									<div>
										<Label
											htmlFor='name'
											className='text-[20px] font-medium text-black'
										>
											Название
										</Label>
										<Input
											type='text'
											id='name'
											className='bg-[#F2F3F4] h-[52px] rounded-[15px] !text-[20px] font-medium'
											value={selectedWarehouse.name}
											readOnly
										/>
									</div>

									<div>
										<Label
											htmlFor='address'
											className='text-[20px] font-medium text-black'
										>
											Адрес
										</Label>
										<Input
											type='text'
											id='address'
											className='bg-[#F2F3F4] h-[52px] rounded-[15px] !text-[20px] font-medium'
											value={selectedWarehouse.adress}
											readOnly
										/>
									</div>

									{/* ==== Роботы ==== */}
									<div>
										<div className='flex justify-between items-center mb-0'>
											<span className='text-[20px] font-medium'>
												Роботы, задействованные на складе
											</span>
											<Button
												variant='outline'
												size='icon'
												aria-label='Add Robot'
												className='small-add-button'
											>
												<AddSmall
													style={{ width: '22px', height: '22px' }}
													fill='#7700FF'
												/>
											</Button>
										</div>

										<div className='max-h-[150px] overflow-y-auto space-y-2'>
											{selectedWarehouse.robots.map(robot => (
												<div
													key={robot.id}
													className='flex justify-between bg-[#F2F3F4] max-h-[52px] rounded-[15px] px-[10px] py-[10px] items-center'
												>
													<span className='text-[18px] font-medium text-black'>
														{robot.id}
													</span>
													<div className='text-right text-[#5A606D] text-[14px]'>
														<div>заряд: {robot.battery_level}%</div>
														<div>статус: {robot.status}</div>
													</div>
												</div>
											))}
										</div>
									</div>

									{/* ==== Товары ==== */}
									<div>
										<div className='grid w-full items-center gap-1'></div>
										<div className='flex justify-between items-center mb-0'>
											<span className='text-[20px] font-medium'>
												Товары на складе
											</span>
											<Button
												variant='outline'
												size='icon'
												aria-label='Add Product'
												className='small-add-button'
											>
												<AddSmall
													style={{ width: '22px', height: '22px' }}
													fill='#7700FF'
												/>
											</Button>
										</div>

										<div className='max-h-[150px] overflow-y-auto space-y-2'>
											{selectedWarehouse.products.map(p => (
												<div
													key={p.name}
													className='flex justify-between bg-[#F2F3F4] max-h-[52px] rounded-[15px] px-[10px] py-[10px] items-center'
												>
													<span className='text-[18px] font-medium text-black'>
														{p.name}
													</span>
													<div className='text-right text-[#5A606D] text-[14px]'>
														<div>статус: {p.category}</div>
														<div>количество: {p.optimal_stock} шт</div>
													</div>
												</div>
											))}
										</div>
									</div>
								</>
							)}
						</section>
					</div>
				</main>
			</div>
		</div>
	)
}

export default ListPage
