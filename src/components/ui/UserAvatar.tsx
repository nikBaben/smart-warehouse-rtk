import { useNavigate } from 'react-router-dom'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'

export function UserAvatar() {
	const navigate = useNavigate()

	return (
		<div
			onClick={() => navigate('/settings')}
			className='cursor-pointer transition-transform hover:scale-105'
			title='Настройки профиля'
		>
			<Avatar>
				<AvatarImage src='https://github.com/shadcn.png' alt='User avatar' />
				<AvatarFallback>CN</AvatarFallback>
			</Avatar>
		</div>
	)
}

export default UserAvatar
