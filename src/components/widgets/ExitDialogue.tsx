import React, { useEffect } from "react";
import { Button } from "../ui/button";
import CheckLarge from "@atomaro/icons/24/navigation/CheckLarge";
import CloseLarge from "@atomaro/icons/24/navigation/CloseLarge";
import Release from '@atomaro/icons/24/action/Release'
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

export function ExitDialogue(){
  const handleExit = async () => {
		localStorage.removeItem('token')
    window.location.href = '/auth'
	}
  return (
		<Dialog>
			<DialogTrigger>
				<button title='Выход' className='transition-transform'>
					<Release
						fill='#9CA3AF'
						className='hover:fill-white cursor-pointer transition-colors duration-200 w-[30px] h-auto'
					/>
				</button>
			</DialogTrigger>
			<DialogContent className='bg-[#F4F4F5] !p-[20px]'>
					<DialogHeader>
						<DialogTitle className='dialog-title-text'>
							Вы точно хотите выйти?
						</DialogTitle>
					</DialogHeader>
					<DialogFooter className='mt-3'>
						<DialogClose asChild>
					    <Button
					    	className='bg-[#7700FF] text-white text-[18px] flex-1 flex items-center gap-[8px] rounded-[10px]'
					    >
					    	<CloseLarge fill='white' />
					    	Остаться
					    </Button>
						</DialogClose>
					  <Button
					  	className='bg-[#FF2626] text-white text-[18px] flex-1 flex items-center gap-[8px] rounded-[10px]'
					  	onClick={handleExit}
					  >
					  	<CheckLarge fill='white' />
					  	Выйти
					  </Button>
					</DialogFooter>
			</DialogContent>
		</Dialog>
	)
};
export default ExitDialogue