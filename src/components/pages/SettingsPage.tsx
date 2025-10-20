import { useState} from "react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import ChevronDown from '@atomaro/icons/24/navigation/ChevronDown';
import { Switch } from "@/components/ui/switch";
import SignOut from '@atomaro/icons/24/navigation/SignOut';
import CheckLarge from '@atomaro/icons/24/navigation/CheckLarge';
import CloseLarge from '@atomaro/icons/24/navigation/CloseLarge';
import { Label } from '@/components/ui/label'
import { Notification } from "@/components/widgets/Notifications";

function SettingsPage(){
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);

    return (
			<div className='flex bg-[#F4F4F5] min-h-screen'>
				<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
					<header className='bg-white h-[60px] w-full flex items-center px-[74px] fixed top-0 left-0 z-[300]'>
						<span className='page-name'>Параметры и уведомления</span>
					</header>
					<main className='flex-1 pt-[70px] pl-[10px] pr-[10px] pb-[10px]'>
						<div className='grid grid-cols-2 gap-6 justify-between'>
							<section className='flex flex-col gap-[10px]'>
								<div className='bg-white rounded-[15px] p-[10px] h-[70px] flex justify-between'>
									<div className='flex items-center gap-[10px]'>
										<div className='avatar'>
											<span className='text-gray-500 text-2xl font-medium'>
												А
											</span>
										</div>
										<div className='flex flex-col text-black'>
											<span className='text-[18px] font-medium'>
												Владимир Смолин
											</span>
											<span className='text-[12px] font-light'>
												логин: vvsmolin@gmail.com
											</span>
										</div>
									</div>
									<span className='flex items-center'> работник склада</span>
								</div>

								<div className='bg-white rounded-[15px] p-[10px] h-[650px] flex flex-col'>
									<h2 className='font-medium text-[24px] mb-[15px]'>
										Профиль и настройки
									</h2>
									<div className='flex flex-col gap-[15px]'>
										<div className='flex flex-col'>
											<Label className='section-title'>Имя</Label>
											<Input className='input'></Input>
										</div>
										<div className='flex flex-col'>
											<span className='section-title'>Фамилия</span>
											<Input className='input'></Input>
										</div>
										<div className='flex flex-col'>
											<Label className='section-title'>Логин</Label>
											<Label className='input-description'>
												Укажите свою почту или номер телефона, чтобы мы могли
												Вас идентифицировать
											</Label>
											<Input className='input'></Input>
										</div>
										<div className='flex flex-col'>
											<Label className='section-title'>
												Почта для отправки отчетов
											</Label>
											<Label className='input-description'>
												Сюда мы будем отправлять Вам отчеты о проверках
											</Label>
											<Input className='input'></Input>
										</div>
										<div className='relative'>
											<span className='section-title'>Роль</span>
											<Button
												className='w-full h-[52px] border-none rounded-[10px] text-[18px] bg-[#F2F3F4] flex justify-between'
												onClick={() => setIsDropdownOpen(!isDropdownOpen)}
											>
												Работник склада
												<ChevronDown
													fill='#9699A3'
													className={`w-[17px] h-[8px] transition-transform duration-200 ${
														isDropdownOpen ? 'rotate-180' : ''
													}`}
												/>
											</Button>

											{isDropdownOpen && (
												<div className='absolute right-0 mt-1 w-auto bg-white border border-gray-300 rounded-[10px] shadow-lg z-50 text-[#7700FF] text-[20px]'>
													<button
														className='w-full text-left px-4 py-2 hover:bg-gray-100'
														onClick={() => console.log('Действие 1')}
													>
														Сигма убийца
													</button>
													<button
														className='w-full text-left px-4 py-2 hover:bg-gray-100'
														onClick={() => console.log('Действие 2')}
													>
														Крутой тип
													</button>
													<button
														className='w-full text-left px-4 py-2 hover:bg-gray-100'
														onClick={() => console.log('Действие 3')}
													>
														Мистер бист
													</button>
												</div>
											)}
										</div>
										<div className='flex gap-[12px] items-center'>
											<Switch
												checked={showNotifications}
												onCheckedChange={setShowNotifications}
												className='data-[state=checked]:bg-[#7700FF] data-[state=unchecked]:bg-gray-300 h-[20px] w-[36px]'
											/>
											<span className='text-[20px]'>
												Отображать уведомления в интерфейсе
											</span>
										</div>
										<div className='flex gap-[10px]'>
											<Button className='flex-1 h-[40px] bg-white border-[2px] border-[#FF4F12] text-[#FF4F12] text-[18px] rounded-[10px]'>
												<SignOut
													fill='#FF4F12'
													className='h-[14px] w-auto'
												></SignOut>
												Выйти
											</Button>
											<Button className='flex-1 h-[40px] bg-white border-[2px] border-[#5A606D] text-[#5A606D] text-[18px] rounded-[10px]'>
												<CloseLarge
													fill='#5A606D'
													className='h-[14px] w-auto'
												></CloseLarge>
												Отменить изменения
											</Button>
											<Button className='flex-1 h-[40px] bg-white border-[2px] border-[#7700FF] text-[#7700FF] text-[18px] rounded-[10px]'>
												<CheckLarge
													fill='#7700FF'
													className='h-[14px] w-auto'
												></CheckLarge>
												Сохранить изменения
											</Button>
										</div>
										<div className='flex items-center justify-center pt-[8px]'>
											<img
												src='/src/assets/images/warehouse-img 1.svg'
												alt='Warehouse'
												className='w-[300px] h-[200px]'
											/>
										</div>
									</div>
								</div>
							</section>
							<section>
								<div className='bg-white rounded-[15px] p-[6px] pl-[12px] flex flex-col justify-between h-[920px]'>
									<div className='flex flex-col p-[10px]'>
										<h2 className='text-[24px] font-medium text-black mb-[10px]'>
											Уведомления
										</h2>
										<Notification />
									</div>
								</div>
							</section>
						</div>
					</main>
				</div>
			</div>
		)
}

export default SettingsPage;