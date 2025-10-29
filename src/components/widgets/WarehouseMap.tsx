'use client'
import { motion } from 'framer-motion'
import { useSocketStore } from '@/store/useSocketStore'
import { useEffect, useRef, useState } from 'react'

import {
  TooltipProvider,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from '@/components/ui/tooltip'
import { Separator } from '@/components/ui/separator'


const GRID_X = 26 // A–Z
const GRID_Y = 50

export function WarehouseMap() {
	const { robotPositions, productSnapshot } = useSocketStore()
	const robots = robotPositions?.robots ?? []
  const products = productSnapshot?.items ?? []

	const containerRef = useRef<HTMLDivElement>(null)
	const [size, setSize] = useState({ width: 1000, height: 600 })

	const getRobotStatusColor = (status: string) => {
		switch (status) {
			case 'idle':
				return '#0ACB5B'
			case 'scanning':
				return '#1F69FF'
			case 'charging':
				return '#FDA610'
			default:
				return '#585D69'
		}
	}

	const getProductStatusColor = (status: string) => {
		switch (status) {
			case 'ok':
				return '#0ACB5B'
			case 'low':
				return '#FDA610'
			case 'critical':
				return '#FF4F12'
			default:
				return '#585D69'
		}
	}

	const getStatusName = (status: string) => {
		switch (status) {
			case 'ok':
				return 'ОК'
			case 'low':
				return 'Низкий остаток'
			case 'critical':
				return 'Критично'
			default:
				return 'Неизвестен'
		}
	}

	//следим за изменением контейнера
	useEffect(() => {
		const container = containerRef.current
		if (!container) return

		const observer = new ResizeObserver(entries => {
			for (const entry of entries) {
				const { width, height } = entry.contentRect
				setSize({ width, height })
			}
		})
		observer.observe(container)
		return () => observer.disconnect()
	}, [])

	const cellWidth = size.width / GRID_X
	const cellHeight = size.height / GRID_Y

	const letters = Array.from({ length: GRID_X }, (_, i) =>
		String.fromCharCode(65 + i)
	)
	const numbers = Array.from({ length: GRID_Y }, (_, i) => i + 1)

	return (
		<div
			ref={containerRef}
			className='relative w-full h-full bg-[#F6F7F7] overflow-hidden rounded-[10px]'
		>
			<svg
				className='absolute top-0 left-0 w-full h-full'
				viewBox={`0 0 ${size.width} ${size.height}`}
				preserveAspectRatio='none'
			>
				{/* СЕТКА */}
				{letters.map((_, i) => (
					<line
						key={`v-${i}`}
						x1={i * cellWidth}
						y1={0}
						x2={i * cellWidth}
						y2={size.height}
						stroke='#aaa'
						strokeDasharray='4'
					/>
				))}
				{numbers.map((_, i) => (
					<line
						key={`h-${i}`}
						x1={0}
						y1={i * cellHeight}
						x2={size.width}
						y2={i * cellHeight}
						stroke='#aaa'
						strokeDasharray='4'
					/>
				))}

				{/* ТОВАРЫ */}
				{products.map((item, index) => (
					<rect
						key={index}
						x={item.current_shelf * cellWidth}
						y={(GRID_Y - item.current_row - 1) * cellHeight}
						width={cellWidth}
						height={cellHeight}
						fill={getProductStatusColor(item.status)}
						opacity={0.8}
						stroke='#ffffff'
						rx={2}
					/>
				))}

				{/* РОБОТЫ */}
				{robots.map((robot, index) => (
					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild>
								<motion.g
									key={index}
									animate={{
										x: robot.x * cellWidth,
										y: (GRID_Y - robot.y) * cellHeight,
									}}
									transition={{ duration: 0.8, ease: 'easeInOut' }}
								>
									<circle
										r={Math.min(cellWidth, cellHeight) * 0.4}
										fill={getRobotStatusColor(robot.status)}
										strokeWidth={0.5}
										stroke='#000000'
									/>
									<text
										className='select-none'
										x={-Math.min(cellWidth, cellHeight) * 0.2}
										y={Math.min(cellWidth, cellHeight) * 0.2}
										fontSize={Math.min(cellWidth, cellHeight) * 0.6}
										fill='white'
										fontWeight='bold'
									>
										{index + 1}
									</text>
								</motion.g>
							</TooltipTrigger>
							<TooltipContent className='bg-[#F7F0FF] p-2 border-[1px] text-[10px] border-[#7700FF]'>
								<p>id: {robot.robot_id}</p>
								<Separator className='bg-[#CECECE]' />
								<p>заряд: {robot.battery_level}%</p>
								<Separator className='bg-[#CECECE]' />
								<p>
									обновлено: &nbsp;
									{new Date(robot.updated_at).toLocaleTimeString('ru-RU', {
										hour: '2-digit',
										minute: '2-digit',
									})}
								</p>
							</TooltipContent>
						</Tooltip>
					</TooltipProvider>
				))}
			</svg>
		</div>
	)
}
