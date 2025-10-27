import axios from 'axios'
import { useState } from 'react'
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '@/components/ui/select'
import { X } from 'lucide-react'
import { Check } from 'lucide-react'
import AddLarge from '@atomaro/icons/24/action/AddLarge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import { useUserStore } from '../../store/useUserStore.tsx'
import { useWarehouseStore } from '../../store/useWarehouseStore.tsx'

export function AddRobotProductDialog() {
  const token = localStorage.getItem('token')
	const [formData, setFormData] = useState({
		name: '',
		article: '',
		category: '',
		stock: '',
		current_row: '',
		current_shelf: '',
		current_position: '',
	})

	const { user } = useUserStore()
	const [loading, setLoading] = useState(false)
  const { selectedWarehouse } = useWarehouseStore()
	
  let denyAdminAccess = !(user?.role === 'operator')

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
		try {
			const [rowPos, shelfPos] = formData.current_position
				.split(',')
				.map(s => s.trim())
			const payload = {
				name: formData.name,
				article: formData.article,
				category: formData.category,
				stock: Number(formData.stock),
				current_row: Number(rowPos),
				current_shelf: shelfPos,
				warehouse_id: selectedWarehouse.id,
			}
      console.log(payload)
			const response = await axios.post(
				'https://dev.rtk-smart-warehouse.ru/api/v1/products',
				payload,
				{
					headers: {
						Authorization: `Bearer ${token}`,
						'Content-Type': 'application/json',
					},
				}
			)

			console.log('Товар добавлен:', response.data)
			toast.success('Товар успешно добавлен!')
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
			toast.error('Не удалось добавить товар')
		} finally {
			/* setLoading(false) */
		}
	}

	return (
		<Dialog>
			<DialogTrigger asChild>
				<Button className='add-warehouse-button' disabled={denyAdminAccess}>
					Добавить робота или устройство
					<AddLarge fill='#7700FF' className='!w-[20px] !h-[20px]' />
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
							<Label className='section-title' htmlFor='address'>
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
							<Label className='section-title' htmlFor='stock'>
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
							<Label className='section-title' htmlFor='stock'>
								Категория товара
							</Label>
							<Select onValueChange={handleCategoryChange}>
								<SelectTrigger className='w-full'>
									<SelectValue placeholder='Выберите категорию' />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value='Смартфоны'>Смартфоны</SelectItem>
									<SelectItem value='Бытовая техника'>
										Бытовая техника
									</SelectItem>
									<SelectItem value='Комплектующие'>Комплектующие</SelectItem>
								</SelectContent>
							</Select>
						</div>
						<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
							<Label className='section-title' htmlFor='current_position'>
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
	)
}
export default AddRobotProductDialog
