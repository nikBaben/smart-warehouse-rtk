import { useState } from 'react'

import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import AddSmall from '@atomaro/icons/24/action/AddSmall'
import { Switch } from '@/components/ui/switch'
import SignOut from '@atomaro/icons/24/navigation/SignOut'
import CheckLarge from '@atomaro/icons/24/navigation/CheckLarge'
import CloseLarge from '@atomaro/icons/24/navigation/CloseLarge'

function ListPage() {
	return (
		<div className='flex bg-[#F4F4F5] min-h-screen'>
			<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
				<header className='bg-white h-[60px] flex items-center px-[14px] z-10'>
					<span className='pagename-font'>Список складов</span>
				</header>
				<main className='flex-1 p-3 h-full'>
					<div className='grid grid-cols-24 gap-3 justify-between h-full'>
						<section className='bg-white rounded-[15px] col-span-10 h-full p-[10px]'>
							<h2 className='section-font'>Список складов</h2>
							<>
								<div className='flex justify-between bg-[#F2F3F4] rounded-[15px] p-[10px]'>
									<div className='flex items-center'>
										<span className='text-[20px] font-medium text-black'>
											YNDX-923212349
										</span>
									</div>
									<div className='text-right space-y-2'>
										<div className='text-[14px] font-normal text-[#5A606D]'>
											город: Уфа
										</div>
										<div className='text-[14px] font-normal text-[#5A606D]'>
											текущее количество товаров: 1432
										</div>
									</div>
								</div>
							</>
						</section>

						<section className='bg-white rounded-[15px] col-span-14 h-full p-[10px] space-y-5'>
							<h2 className='section-font'>Подробная информация о складе</h2>
							<div>
								<div className='grid w-full items-center gap-1'>
									<Label
										htmlFor='Название'
										className='text-[20px] font-medium text-black'
									>
										Название
									</Label>
									<Input
										type='name'
										id='name'
										className='bg-[#F2F3F4] h-[52px] rounded-[10px] !text-[20px] font-medium'
										placeholder='Название склада'
									/>
								</div>
							</div>
							<div>
								<div className='grid w-full items-center gap-1'>
									<Label
										htmlFor='Адрес'
										className='dashboard-section-font'
									>
										Адрес
									</Label>
									<Input
										type='name'
										id='name'
										className='bg-[#F2F3F4] h-[52px] rounded-[10px] !text-[20px] font-medium'
										placeholder='Адрес склада'
									/>
								</div>
							</div>
							<div>
								<div className='grid w-full items-center gap-1'>
									<div className='flex justify-between'>
										<span className='text-[20px] font-medium'>
											Роботы, задействованные на складе
										</span>
										<Button
											variant='outline'
											size='icon'
											aria-label='Submit'
											className='
												w-[22px] h-[22px] 
												border border-[#CCCCCC] 
												hover:border-[#7700FF]
												rounded-[4px]
												flex items-center justify-center
												transition-all duration-200
												hover:shadow-[0_0_15px_rgba(119,0,255,0.2)]
											'
										>
											<AddSmall/>
										</Button>
									</div>

									<div className='flex justify-between bg-[#F2F3F4] rounded-[15px] p-[10px]'>
										<div className='flex items-center'>
											<span className='text-[20px] font-medium text-black'>
												ID-1032
											</span>
										</div>
										<div className='text-right space-y-0'>
											<div className='text-[16px] font-normal text-[#5A606D]'>
												заряд: 75%
											</div>
											<div className='text-[16px] font-normal text-[#5A606D]'>
												статус: активен
											</div>
										</div>
									</div>
								</div>
							</div>
						</section>
					</div>
				</main>
			</div>
		</div>
	)
}
export default ListPage
