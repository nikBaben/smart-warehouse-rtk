import { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import AddSmall from '@atomaro/icons/24/action/AddSmall'

type Warehouse = {
	id: string
	city: string
	itemsCount: number
	robots: { id: string; charge: number; status: string }[]
	products: { name: string; status: string; quantity: number }[]
}

function ListPage() {
	const [warehouses, setWarehouses] = useState<Warehouse[]>([])
	const [selectedWarehouse, setSelectedWarehouse] = useState<Warehouse | null>(
		null
	)

	//Заглушка для теста (позже заменишь на fetch)
	useEffect(() => {
		setWarehouses([
			{
				id: 'YNDX-923212349',
				city: 'Уфа',
				itemsCount: 1432,
				robots: [
					{ id: 'ID-1032', charge: 75, status: 'активен' },
					{ id: 'ID-1099', charge: 58, status: 'на подзарядке' },
				],
				products: [
					{
						name: 'Apple iPhone 17 Pro Max - 012034',
						status: 'низкий остаток',
						quantity: 20,
					},
					{
						name: 'Samsung Galaxy S25 Ultra',
						status: 'в наличии',
						quantity: 144,
					},
				],
			},
			{
				id: 'YNDX-923212350',
				city: 'Москва',
				itemsCount: 980,
				robots: [{ id: 'ID-2031', charge: 90, status: 'активен' }],
				products: [
					{ name: 'Xiaomi 15 Pro', status: 'в наличии', quantity: 300 },
				],
			},
		])
	}, [])

	// 📡 Здесь ты потом заменишь на реальный запрос к API
	// useEffect(() => {
	//   fetch("/api/warehouses")
	//     .then((res) => res.json())
	//     .then(setWarehouses)
	//     .catch(console.error);
	// }, []);

	const handleSelect = (warehouse: Warehouse) => {
		setSelectedWarehouse(prev => (prev?.id === warehouse.id ? null : warehouse))
	}

	return (
		<div className='flex bg-[#F4F4F5] min-h-screen'>
			<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
				<header className='bg-white h-[60px] flex items-center px-[14px] z-10'>
					<span className='pagename-font'>Список складов</span>
				</header>

				<main className='flex-1 p-3 h-full'>
					<div className='grid grid-cols-24 gap-3 justify-between h-full'>
						{/* ====== Список складов ====== */}
						<section className='bg-white rounded-[15px] col-span-10 h-full p-[10px] overflow-y-auto'>
							<h2 className='big-section-font mb-3'>Список складов</h2>

							<div className='space-y-2'>
								{warehouses.map(wh => (
									<div
										key={wh.id}
										onClick={() => handleSelect(wh)}
										className={`flex justify-between items-center bg-[#F2F3F4] max-h-[52px] rounded-[15px] px-[10px] py-[10px] cursor-pointer transition-all border-[2px]
                    ${
											selectedWarehouse?.id === wh.id
												? 'border-[2px] border-[#7700FF] shadow-[0_0_10px_rgba(119,0,255,0.3)]'
												: 'border border-transparent hover:border-[2px] hover:border-[#7700FF33] hover:shadow-[0_0_10px_rgba(119,0,255,0.3)]'
										}`}
									>
										<div className='flex items-center'>
											<span className='text-[20px] font-medium text-black'>
												{wh.id}
											</span>
										</div>
										<div className='text-right space-y-0'>
											<div className='text-[14px] font-normal text-[#5A606D]'>
												город: {wh.city}
											</div>
											<div className='text-[14px] font-normal text-[#5A606D]'>
												текущее количество товаров: {wh.itemsCount}
											</div>
										</div>
									</div>
								))}
							</div>
						</section>

						{/* ====== Панель подробностей ====== */}
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
											value={selectedWarehouse.id}
											readOnly
										/>
									</div>

									<div>
										<Label
											htmlFor='address'
											className='text-[20px] font-medium text-black'
										>
											Город
										</Label>
										<Input
											type='text'
											id='address'
											className='bg-[#F2F3F4] h-[52px] rounded-[15px] !text-[20px] font-medium'
											value={selectedWarehouse.city}
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
														<div>заряд: {robot.charge}%</div>
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
														<div>статус: {p.status}</div>
														<div>количество: {p.quantity} шт</div>
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
