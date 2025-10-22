import axios from 'axios'
import { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import AddSmall from '@atomaro/icons/24/action/AddSmall'
import { UserAvatar } from '../ui/UserAvatar.tsx'
import { AddWarehouseDialog } from '../ui/AddWarehouseDialog.tsx'
import { Check } from 'lucide-react'
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
	name: string
	article: string
	category: string
	stock: number
	current_row: number
	current_shelf: string
	current_position: string
	status: string
}

type Warehouse = {
	name: string
	address: string
	products_count: number
	id: string
}

function ListPage() {
	//-----ОБРАБОТКА СОСТОЯНИЙ-----
	const [warehouses, setWarehouses] = useState<Warehouse[]>([])
	const [selectedWarehouse, setSelectedWarehouse] = useState<Warehouse | null>(null)
	
	
	const [formData, setFormData] = useState({
		name: '',
		article: '',
		category: '',
		stock: '',
		current_row: '',
		current_shelf: '',
		current_position: '',
	})
	
	const [robots, setRobots] = useState<WhRobot[]>([])
	
	const [products, setProducts] = useState<WhProduct[]>([])
	
	const [editedWarehouse, setEditedWarehouse] = useState({
		name: '',
		address: '',
	})

	const [editedProduct, setEditedProduct] = useState<WhProduct | null>(null)
	
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState<string | null>(null)
	

	//-----ЗАГРУЗКА СПИСКА СКЛАДОВ-----
	useEffect(() => {
		const fetchWarehouses = async () => {
			try {
				const response = await axios.get(
					'https://rtk-smart-warehouse.ru/api/v1/warehouse/all',
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

	useEffect(() => {
		if (selectedWarehouse) {
			setEditedWarehouse({
				name: selectedWarehouse.name || '',
				address: selectedWarehouse.address || '',
			})
		}
	}, [selectedWarehouse])

	const handleSelectWarehouse = async (warehouse: Warehouse) => {
		if(selectedWarehouse?.id == warehouse.id){
			setSelectedWarehouse(null)
			setRobots([])
			setProducts([])
			return
		}

		setSelectedWarehouse(warehouse)
		setLoading(true)
		setError(null)

		setRobots([]) //очистка старых полей при выборе склада
		setProducts([])

		try {
			const warehouseById = await axios.get(
				`https://rtk-smart-warehouse.ru/api/v1/robots/get_robots_by_warehouse_id/${warehouse.id}`
			)
			console.log('Данные склада:', warehouseById.data)
			
			const robotsById = await axios.get(
				`https://rtk-smart-warehouse.ru/api/v1/robots/get_robots_by_warehouse_id/${warehouse.id}`
			)
			console.log('Роботы на складе:',robotsById.data)
			setRobots(robotsById.data)

			const productsById = await axios.get(
				`https://rtk-smart-warehouse.ru/api/v1/products/get_products_by_warehouse_id/${warehouse.id}`
			)
			console.log('Товары на складе:', productsById.data)
			setProducts(productsById.data)

		} catch (err) {
			console.log('Ошибка загрузки подробностей склада:', err)
		}
		finally{
			setLoading(false)
		}
	}

	const handleAddRobot = async() => {
		if (!selectedWarehouse)
			return alert('Выберите склад для добавления робота.')
		try {
			const payload = {
				warehouse_id: selectedWarehouse.id,
			}

			const response = await axios.post(
				'https://rtk-smart-warehouse.ru/api/v1/robots',
				payload,
				{ headers: { 'Content-Type': 'application/json' } }
			)

			console.log('Робот успешно добавлен:', response.data)
			alert('Робот успешно добавлен!')

			// обновляем список роботов для текущего склада
			const robotsResponse = await axios.get(
				`https://rtk-smart-warehouse.ru/api/v1/robots/get_robots_by_warehouse_id/${selectedWarehouse.id}`
			)
			setRobots(robotsResponse.data)
		} catch (error) {
			console.error('Ошибка при добавлении робота:', error)
			alert('Не удалось добавить робота')
		}
	}

	const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const { name, value } = e.target
		setEditedWarehouse(prev => ({ ...prev, [name]: value }))
	}

	const handleSave = async (field: 'name' | 'address') => {
		if (!selectedWarehouse) return

		try {
			const updatedData = {
				...selectedWarehouse,
				[field]: editedWarehouse[field],
			}

			const response = await axios.put(
				`https://rtk-smart-warehouse.ru/api/v1/warehouse/${selectedWarehouse.id}`,
				updatedData,
				{ headers: { 'Content-Type': 'application/json' } }
			)

			console.log('Обновлено:', response.data)
			alert('Данные склада успешно обновлены!')

			// обновляем данные в состоянии
			setSelectedWarehouse(response.data)
		} catch (error) {
			console.error('Ошибка при обновлении склада:', error)
			alert('Не удалось сохранить изменения')
		}
	}

	const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const { name, value } = e.target
		setFormData(prev => ({ ...prev, [name]: value }))
	}
	const handleCategoryChange = (value: string) => {
		setFormData(prev => ({ ...prev, category: value }))
	}

	const handleAddProduct = async (e: React.FormEvent) => {
	  e.preventDefault()

	  if (!selectedWarehouse) {
	    alert('Сначала выберите склад')
	    return
	  }

	  setLoading(true)
	  try {
			const [rowPos, shelfPos] = formData.current_position.split(',').map(s => s.trim())	
	    const payload = {
				name: formData.name,
				article: formData.article,
				category: formData.category,
				stock: Number(formData.stock),
				current_row: Number(rowPos),
				current_shelf: shelfPos,
				warehouse_id: selectedWarehouse.id,
			}

	    const response = await axios.post(
	      'https://rtk-smart-warehouse.ru/api/v1/products',
	      payload,
	      { headers: { 'Content-Type': 'application/json' } }
	    )

	    console.log('Товар добавлен:', response.data)
	    alert('Товар успешно добавлен!')

	    //обновляем список товаров текущего склада
	    const updatedProducts = await axios.get(
	      `https://rtk-smart-warehouse.ru/api/v1/products/get_products_by_warehouse_id/${selectedWarehouse.id}`
	    )
	    setProducts(updatedProducts.data)

	    //очистка формы
	    setFormData({
				name: '',
				article: '',
				category: '',
				stock: '',
				current_row: '',
				current_shelf: '',
				current_position: '',
			})
	  } catch (error) {
	    console.error('Ошибка при добавлении товара:', error)
	    alert('Не удалось добавить товар')
	  } finally {
	    setLoading(false)
	  }
	}

	const handleProductEditChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const { name, value } = e.target
		setEditedProduct(prev => (prev ? { ...prev, [name]: value } : prev))
	}

	const handleUpdateProduct = async (e: React.FormEvent) => {
		e.preventDefault()
		if (!selectedWarehouse || !editedProduct) return

		setLoading(true)
		try {
			const [rowPos, shelfPos] =
				editedProduct.current_position?.split(',').map(s => s.trim()) || []

			const payload = {
				name: editedProduct.name,
				article: editedProduct.article,
				category: editedProduct.category,
				stock: Number(editedProduct.stock),
				current_row: Number(rowPos),
				current_shelf: shelfPos,
				warehouse_id: selectedWarehouse.id,
			}

			await axios.put(
				`https://rtk-smart-warehouse.ru/api/v1/products/{editedProduct.id}`,
				payload,
				{ headers: { 'Content-Type': 'application/json' } }
			)

			alert('Изменения успешно сохранены!')

			// обновляем список товаров
			const updatedProducts = await axios.get(
				`https://rtk-smart-warehouse.ru/api/v1/products/get_products_by_warehouse_id/${selectedWarehouse.id}`
			)
			
			setProducts(updatedProducts.data)
		} catch (error) {
			console.error('Ошибка при обновлении товара:', error)
			alert('Не удалось обновить товар')
		} finally {
			setLoading(false)
		}
	}

	return (
		<div className='flex bg-[#F4F4F5] min-h-screen'>
			<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
				<header className='bg-white justify-between flex items-center h-[60px] px-[14px] z-10'>
					<span className='pagename-font'>Список складов</span>
					<div className='flex items-center space-x-5'>
						<AddWarehouseDialog />
						<UserAvatar />
					</div>
				</header>

				<main className='flex-1 p-3 h-full'>
					<div className='grid grid-cols-24 gap-3 justify-between h-full'>
						<section className='bg-white rounded-[15px] col-span-10 h-full p-[10px] overflow-y-auto'>
							<h2 className='big-section-font mb-3'>Список складов</h2>
							<div className='space-y-2'>
								{warehouses.map(wh => (
									<div
										key={wh.name}
										onClick={() => handleSelectWarehouse(wh)}
										className={`flex justify-between items-center bg-[#F2F3F4] rounded-[10px] max-h-[60px] px-[10px] py-[10px] cursor-pointer transition-all border-[2px]
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
												город: {wh.address}
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
							<h2 className='big-section-font'>
								Подробная информация о складе
							</h2>

							{!selectedWarehouse ? (
								<div className='flex items-center justify-center font-medium text-center h-full text-[#9699A3] text-[24px]'>
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
										<div className='flex w-full items-center gap-2'>
											<Input
												type='text'
												id='name'
												name='name'
												className='main-input'
												value={editedWarehouse.name}
												onChange={handleInputChange}
											/>
											<Button
												type='submit'
												className='warehouse-save-changes-button'
												onClick={() => handleSave('name')}
												disabled={
													editedWarehouse.name == selectedWarehouse.name
												}
											>
												Сохранить
											</Button>
										</div>
									</div>

									<div>
										<Label
											htmlFor='address'
											className='text-[20px] font-medium text-black'
										>
											Адрес
										</Label>
										<div className='flex w-full items-center gap-2'>
											<Input
												type='text'
												id='address'
												name='address'
												className='main-input'
												value={editedWarehouse.address}
												onChange={handleInputChange}
											/>
											<Button
												type='submit'
												className='warehouse-save-changes-button'
												onClick={() => handleSave('address')}
												disabled={
													editedWarehouse.address == selectedWarehouse.address
												}
											>
												Сохранить
											</Button>
										</div>
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
												onClick={handleAddRobot}
											>
												<AddSmall
													style={{ width: '22px', height: '22px' }}
													fill='#7700FF'
												/>
											</Button>
										</div>

										<div className='max-h-[770px] overflow-y-auto space-y-2'>
											{robots.map(robot => (
												<div
													key={robot.id}
													className='flex justify-between bg-[#F2F3F4] max-h-[52px] rounded-[10px] px-[10px] py-[10px] items-center'
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
										{/* 										<div className='grid w-full items-center gap-1'></div> */}
										<div className='flex justify-between items-center mb-0'>
											<span className='text-[20px] font-medium'>
												Товары на складе
											</span>
											<Dialog>
												<DialogTrigger asChild>
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
												</DialogTrigger>
												<DialogContent className='bg-[#F4F4F5] !p-[20px] !w-[558px]'>
													<form onSubmit={handleAddProduct}>
														<DialogHeader>
															<DialogTitle className='dialog-title-text'>
																Добавление товара
															</DialogTitle>
														</DialogHeader>
														<div className='grid gap-4'>
															<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																<Label className='section-title' htmlFor='name'>
																	Укажите название вашего товара
																</Label>
																<Input
																	className='dialog-input-placeholder-text'
																	id='name'
																	name='name'
																	value={formData.name}
																	onChange={handleChange}
																	placeholder='Например, Apple IPhone 17'
																	required
																/>
															</div>
															<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																<Label
																	className='section-title'
																	htmlFor='address'
																>
																	Введите артикул товара
																</Label>
																<Input
																	className='dialog-input-placeholder-text'
																	id='article'
																	name='article'
																	value={formData.article}
																	onChange={handleChange}
																	placeholder='Например, 9573420'
																	required
																/>
															</div>
															<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																<Label
																	className='section-title'
																	htmlFor='stock'
																>
																	Количество единиц товара (шт)
																</Label>
																<Input
																	className='dialog-input-placeholder-text'
																	id='stock'
																	name='stock'
																	value={formData.stock}
																	onChange={handleChange}
																	placeholder='100'
																	required
																/>
															</div>
															<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																<Label
																	className='section-title'
																	htmlFor='stock'
																>
																	Категория товара
																</Label>
																<Select onValueChange={handleCategoryChange}>
																	<SelectTrigger className='w-full'>
																		<SelectValue placeholder='Выберите категорию' />
																	</SelectTrigger>
																	<SelectContent>
																		<SelectItem value='Смартфоны'>
																			Смартфоны
																		</SelectItem>
																		<SelectItem value='Бытовая техника'>
																			Бытовая техника
																		</SelectItem>
																		<SelectItem value='Комплектующие'>
																			Комплектующие
																		</SelectItem>
																	</SelectContent>
																</Select>
															</div>
															<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																<Label
																	className='section-title'
																	htmlFor='current_position'
																>
																	Где расположен товар?
																</Label>
																<Input
																	className='dialog-input-placeholder-text'
																	id='current_position'
																	name='current_position'
																	value={formData.current_position}
																	onChange={handleChange}
																	placeholder='Координаты сектора, в формате 1-50, A-Z'
																	required
																/>
															</div>
														</div>
														<DialogFooter className='mt-2'>
															<DialogClose asChild>
																<Button className='w-[50%] items-center rounded-[10px] text-[18px] text-white font-medium bg-[#FF4F12] cursor-pointer transition-all hover:brightness-90'>
																	<X className='!h-5 !w-5' />
																	Отмена
																</Button>
															</DialogClose>
															<Button
																type='submit'
																className='w-[50%] rounded-[10px] text-[18px] text-white font-medium bg-[#7700FF] cursor-pointer transition-all hover:brightness-90'
																disabled={loading}
															>
																<Check className='!h-5 !w-5' />
																{loading ? 'Добавление...' : 'Подтвердить'}
															</Button>
														</DialogFooter>
													</form>
												</DialogContent>
											</Dialog>
										</div>

										<div className='!max-h-[200px] overflow-y-auto space-y-2'>
											{products.map(p => (
												<Dialog>
													<DialogTrigger
														className='w-full'
														onClick={() => setEditedProduct(p)}
													>
														<Button
															aria-label='Add Product'
															className='product-button'
														>
															<div key={p.name} className='product-button-elem'>
																<span className='text-[18px] font-medium text-black'>
																	{p.name}
																</span>
																<div className='text-right text-[#5A606D] text-[14px]'>
																	<div>статус: {p.status}</div>
																	<div>количество: {p.stock} шт</div>
																</div>
															</div>
														</Button>
													</DialogTrigger>
													<DialogContent className='bg-[#F4F4F5] !p-[20px] !w-[558px]'>
														<form onSubmit={handleUpdateProduct}>
															<DialogHeader>
																<DialogTitle className='dialog-title-text'>
																	Просмотр и редактирование
																</DialogTitle>
															</DialogHeader>
															<div className='grid gap-4'>
																<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																	<Label
																		className='section-title'
																		htmlFor='name'
																	>
																		Название товара
																	</Label>
																	<Input
																		className='dialog-input-placeholder-text'
																		id='name'
																		name='name'
																		value={editedProduct?.name}
																		onChange={handleProductEditChange}
																		placeholder='Например, Apple IPhone 17'
																		required
																	/>
																</div>
																<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																	<Label
																		className='section-title'
																		htmlFor='address'
																	>
																		Артикул товара
																	</Label>
																	<Input
																		className='dialog-input-placeholder-text'
																		id='article'
																		name='article'
																		value={editedProduct?.article}
																		onChange={handleProductEditChange}
																		placeholder='Например, 9573420'
																		required
																	/>
																</div>
																<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																	<Label
																		className='section-title'
																		htmlFor='stock'
																	>
																		Количество единиц товара (шт)
																	</Label>
																	<Input
																		className='dialog-input-placeholder-text'
																		id='stock'
																		name='stock'
																		value={editedProduct?.stock}
																		onChange={handleProductEditChange}
																		placeholder='100'
																		required
																	/>
																</div>
																<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																	<Label
																		className='section-title'
																		htmlFor='stock'
																	>
																		Категория товара
																	</Label>
																	<Select
																		value={editedProduct?.category}
																		onValueChange={value =>
																			setEditedProduct(prev =>
																				prev
																					? { ...prev, category: value }
																					: prev
																			)
																		}
																	>
																		<SelectTrigger className='w-full'>
																			<SelectValue placeholder='Выберите категорию' />
																		</SelectTrigger>
																		<SelectContent>
																			<SelectItem value='Смартфоны'>
																				Смартфоны
																			</SelectItem>
																			<SelectItem value='Бытовая техника'>
																				Бытовая техника
																			</SelectItem>
																			<SelectItem value='Комплектующие'>
																				Комплектующие
																			</SelectItem>
																		</SelectContent>
																	</Select>
																</div>
																<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
																	<Label
																		className='section-title'
																		htmlFor='current_position'
																	>
																		Где расположен товар?
																	</Label>
																	<Input
																		className='dialog-input-placeholder-text'
																		id='current_position'
																		name='current_position'
																		value={`${editedProduct?.current_row}, ${editedProduct?.current_shelf}`}
																		onChange={handleProductEditChange}
																		placeholder='Координаты сектора, в формате 1-50, A-Z'
																		required
																	/>
																</div>
															</div>
															<DialogFooter className='mt-2'>
																<DialogClose asChild>
																	<Button className='w-[50%] items-center rounded-[10px] text-[18px] text-white font-medium bg-[#FF4F12] cursor-pointer transition-all hover:brightness-90'>
																		<X className='!h-5 !w-5' />
																		Отмена
																	</Button>
																</DialogClose>
																<Button
																	type='submit'
																	className='w-[50%] rounded-[10px] text-[18px] text-white font-medium bg-[#7700FF] cursor-pointer transition-all hover:brightness-90'
																	disabled={loading}
																>
																	<Check className='!h-5 !w-5' />
																	{loading ? 'Изменение...' : 'Подтвердить'}
																</Button>
															</DialogFooter>
														</form>
													</DialogContent>
												</Dialog>
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
