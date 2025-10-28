import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { motion } from "framer-motion";
import { useSocketStore } from '@/store/useSocketStore.tsx'

export function RobotActivityChart(){
	const { activitySeries } = useSocketStore()

	const data = activitySeries?.series.map(([iso,value])=>({
		time: new Date(iso).toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
		}), 
		value,
	})) || []
	console.log('📊 activitySeries:', activitySeries)

  return (
		<div className='w-full h-full flex items-center justify-center'>
			<ResponsiveContainer width='100%' height='100%'>
				<LineChart
					data={data}
					margin={{ top: 5, right: 28, left: -10, bottom: 5 }}
				>
					<CartesianGrid stroke='#CCCCCC' />
					<XAxis
						dataKey='time'
						tick={{ fontSize: 10, fill: '#000000' }}
						label={{
							value: 'мин',
							position: 'insideRight',
							dy: -3.5,
							offset: -9,
							style: { textAnchor: 'start', fontSize: 10, fill: '#000000' },
						}}
						axisLine={false}
						tickLine={false}
					/>
					<YAxis
						domain={[0, 100]}
						tickFormatter={val => `${val}%`}
						interval={0}
						tick={{ fontSize: 10, fill: '#000000' }}
						axisLine={false}
						tickLine={false}
						dx={-10}
					/>
					<Tooltip
						formatter={(value: number) => [`активность: ${value}%`]}
						labelFormatter={(label: string) => `время: ${label} мин`}
					/>
					<motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
						<Line
							type='linear'
							dataKey='value'
							stroke='#7700FF'
							strokeWidth={1.5}
							dot={{ r: 2 }}
							activeDot={{ r: 4 }}
						/>
					</motion.g>
				</LineChart>
			</ResponsiveContainer>
		</div>
	)
};