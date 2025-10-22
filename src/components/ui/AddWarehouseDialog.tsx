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
import { X } from 'lucide-react'
import { Check } from 'lucide-react'
import AddLarge from '@atomaro/icons/24/action/AddLarge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function AddWarehouseDialog(){
  const [formData, setFormData] = useState({
		name: '',
		address: '',
		max_products: '',
	})
  
  const [loading, setLoading] = useState(false)
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const{name,value} = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
    const payload = {
			name: formData.name,
			address: formData.address,
			max_products: Number(formData.max_products),
		}

			const response = await axios.post(
				'http://51.250.97.137:8001/api/v1/warehouse',
				payload,
				{ headers: { 'Content-Type': 'application/json' } }
			)

			console.log('Склад успешно добавлен:', response.data)
			alert('Склад успешно добавлен!')
			setFormData({ name: '', address: '', max_products: '', })
		} catch (error) {
			console.error('Ошибка при добавлении склада:', error)
			alert('Ошибка при добавлении склада')
		} finally {
			setLoading(false)
		}
  }

  return (
		<Dialog>
			<DialogTrigger asChild>
				<Button className='add-warehouse-button'>
					Добавить склад
					<AddLarge fill='#7700FF' className='!w-[20px] !h-[20px]' />
				</Button>
			</DialogTrigger>
			<DialogContent className='bg-[#F4F4F5] !p-[10px] !w-[558px]'>
				<form onSubmit={handleSubmit}>
					<DialogHeader>
						<DialogTitle className='dialog-title-text'>
							Добавление склада
						</DialogTitle>
					</DialogHeader>
					<div className='grid gap-4'>
						<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
							<Label className='section-title' htmlFor='name'>
								Название склада
							</Label>
							<Input
								className='dialog-input-placeholder-text'
								id='name'
								name='name'
								value={formData.name}
								onChange={handleChange}
								placeholder='Например, WB-1475349'
								required
							/>
						</div>
						<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
							<Label className='section-title' htmlFor='address'>
								Адрес склада
							</Label>
							<Input
								className='dialog-input-placeholder-text'
								id='address'
								name='address'
								value={formData.address}
								onChange={handleChange}
								placeholder='г. Санкт-Петербург, ул. Пушкина, д. 14 '
								required
							/>
						</div>
						<div className='grid gap-3 bg-white p-[10px] rounded-[10px]'>
							<Label className='section-title' htmlFor='max_products'>
								Вместимость склада
							</Label>
							<Input
								className='dialog-input-placeholder-text'
								id='max_products'
								name='max_products'
								value={formData.max_products}
								onChange={handleChange}
								placeholder='Укажите максимальную вместимость склада'
								required
							/>
						</div>
					</div>
					<DialogFooter>
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
export default AddWarehouseDialog