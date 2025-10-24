import axios from 'axios'
import { AxiosError } from 'axios'
import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { useNavigate } from 'react-router-dom'
import { Header } from '@/components/ui/header'
import { Footer } from '@/components/ui/footer'
import { toast } from 'sonner'

{
	/*вообще временная фигня, потом на нормальную маску поменяю*/
}
function AuthPage() {
	const [email, setEmail] = useState('')
	const [password, setPassword] = useState('')
	const [loading, setLoading] = useState(false)

	const navigate = useNavigate()

	const handleLogin = async () => {
		setLoading(true)

		const token = localStorage.getItem('token')
		const payload = { email, password }
		try{
			const response = await axios.post ('https://rtk-smart-warehouse.ru/api/v1/auth/login', payload, {
					headers: {
						'Content-Type': 'application/json',
					},
				}
			)
			localStorage.setItem('token', response.data.token)
			navigate('/')
		}
		catch(error){
			const err = error as AxiosError<{ error?: string }>
			const message = err.response?.data?.error || 'Неизвестная ошибка'
			if (err.response){
				toast.error('Ошибка при входе в аккаунт', {
      	  description: message,
				})
			}
			else {
				alert('Ошибка входа: Сервер недоступен или нет ответа')
			}	
		}
		finally{
			setLoading(false)
		}
	}

	return (
		<div className='min-h-screen flex flex-col bg-[#F4F4F5] text-gray-900 font-rostelecom'>
			<Header />
			<main className='flex-1 flex flex-col items-center justify-center p-4 relative'>
				<div className='flex flex-col gap-[20px]'>
					<div className='w-[430px] h-[550px] bg-white rounded-[15px] overflow-hidden max-w-md p-8 flex flex-col items-center'>
						<div className='w-full m-[20px] h-[68px] flex flex-col gap-[20px]'>
							<h1 className='text-2xl font-bold flex flex-col items-center justify-center'>
								Войти на склад
							</h1>
							<div className='flex flex-col items-center justify-center'>
								<Input
									placeholder='Телефон, почта или логин'
									value={email}
									onChange={e => setEmail(e.target.value)}
									className='w-[365px] h-[68px] rounded-[10px] border-none bg-[#F2F3F4] placeholder-[#A1A1AA] placeholder:font-medium placeholder:text-[18px] placeholder:leading-[24px] shadow-none !text-[18px] !leading-[24px] !text-[#000000] !font-medium'
								/>
							</div>
							<div className='flex flex-col gap-[20px]'>
								<div className='flex flex-col items-center justify-center'>
									<Input
										type='password'
										placeholder='Пароль'
										value={password}
										onChange={e => setPassword(e.target.value)}
										className='w-[365px] h-[68px] rounded-[10px] border-none bg-[#F2F3F4] placeholder-[#A1A1AA] placeholder:font-medium placeholder:text-[18px] placeholder:leading-[24px] shadow-none !text-[18px] !leading-[24px] !text-[#000000] !font-medium'
									/>
								</div>
								<div className='flex items-center space-x-2'>
									<Checkbox
										className={`
                        cursor-pointer
                        shadow-none
                        peer
                        w-5 h-5 border-1 rounded-[5px]
                        bg-[#F2F3F4] border-[#F2F3F4]
                        data-[state=checked]:bg-[#F2F3F4]
                        data-[state=checked]:text-[#7700FF]
                        data-[state=checked]:border-[#7700FF]
                        transition-colors duration-200
                        flex items-center justify-center`}
									/>
									<span className='text-[#000000] text-[16px] leading-[24px]'>
										Запомнить меня
									</span>
								</div>
							</div>
							<div className='flex flex-col items-center justify-center'>
								<Button
									disabled={!email || !password || loading}

									onClick={handleLogin}
									className={`w-[365px] cursor-pointer h-[68px] rounded-[10px] text-[18px] leading-[24px] shadow-none ${
										!email || !password
											? 'bg-[#CECECE] text-[#FFFFFF] cursor-not-allowed'
											: 'bg-[#7700FF] text-[#FFFFFF]'
									}`}
								>
									{loading? 'Загрузка...' : 'Войти'}
								</Button>
							</div>
							<div className='flex flex-col items-center justify-center'>
								<Button
									variant='outline'
									className='cursor-pointer w-[365px] h-[68px] rounded-[10px] text-[18px] leading-[24px] text-[#7700FF] border-none bg-[#F7F0FF] shadow-none'
								>
									Зарегистрироваться
								</Button>
							</div>
							<p className='text-[18px] leading-[24px] text-[#9699A3] text-center'>
								<span className='hover:underline cursor-pointer'>
									Забыли пароль?
								</span>
							</p>
						</div>
					</div>

					<div className='w-full h-[123px] bg-white rounded-[15px] overflow-hidden max-w-md relative'>
						<p className='absolute top-[10px] text-center w-full text-[18px] text-[#9699A3]'>
							Войти через
						</p>
						<div className='absolute top-[50px] flex items-center justify-center gap-[17px] w-full'>
							<Button
								className='w-[174px] h-[50px] px-[56px] py-[5px] rounded-[10px] text-[18px] flex items-center justify-center hover:opacity-90 bg-[#FFF1EC] text-[#FF4F12] shadow-none'
								disabled
							>
								Ростелеком ID
							</Button>

							<Button className='cursor-pointer w-[174px] h-[50px] px-[56px] py-[5px] rounded-[10px] text-[18px] flex items-center justify-center hover:opacity-90 bg-[#FFF1EC] text-[#FF4F12] shadow-none'>
								Код доступа
							</Button>
						</div>
					</div>
				</div>
				<Footer />
			</main>
		</div>
	)
}

export default AuthPage
