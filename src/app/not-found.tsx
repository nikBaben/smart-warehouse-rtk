import { Button } from '@/components/ui/button'
import { motion } from 'framer-motion'
function NotFound() {
	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			className='flex flex-col items-center justify-center h-[80vh] text-center'
		>
			<div className='relative space-y-[-80px]'>
				<h1 className='select-none font-bold text-[#7700FF] text-[300px] relative z-10'>
					404
				</h1>
				<h1 className='select-none font-bold text-[#FF4F12] text-[300px] absolute top-3 left-3 z-0'>
					404
				</h1>
			</div>
			<p className='text-[#9699A3] text-[30px] mb-6'>
				страницы с таким именем не существует, или она была перемещена в другой
				раздел
			</p>
			<a
				href='/'
				className='text-[#9699A3] text-[30px] mt-10 hover:text-[#7700FF] underline cursor-pointer'
			>
				на главную
			</a>
		</motion.div>
	)
}
export default NotFound
