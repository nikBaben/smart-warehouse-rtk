import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@/components/ui/dialog";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { motion } from "framer-motion";

{/*временные данные пока что*/}

const data = [
  { week: 1, iphone: 120, nanotubes: 320, tv: 450 },
  { week: 2, iphone: 200, nanotubes: 420, tv: 380 },
  { week: 3, iphone: 90, nanotubes: 470, tv: 300 },
  { week: 4, iphone: 160, nanotubes: 250, tv: 280 },
  { week: 5, iphone: 180, nanotubes: 310, tv: 340 },
  { week: 6, iphone: 460, nanotubes: 0, tv: 470 },
  { week: 7, iphone: 410, nanotubes: 120, tv: 60 },
  { week: 8, iphone: 420, nanotubes: 180, tv: 310 },
  { week: 9, iphone: 440, nanotubes: 460, tv: 320 },
  { week: 10, iphone: 390, nanotubes: 340, tv: 410 },
  { week: 11, iphone: 60, nanotubes: 90, tv: 360 },
  { week: 12, iphone: 150, nanotubes: 300, tv: 80 },
];

export function TrendGraph({ onClose }: { onClose: () => void }) {
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="w-[700px] h-[270px] py-0 top-[35%] bg-white z-[500] rounded-[15px] p-0 gap-0 flex flex-col items-center justify-center">
        <DialogHeader className="w-full px-[20px]">
          <DialogTitle className="text-[20px] font-medium text-black text-left">
            График тренда остатков
          </DialogTitle>
        </DialogHeader>
        <div className="flex w-[657px] h-[210px] items-center">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 0, right: 25, left: -30, bottom: 0 }}
            >
              <CartesianGrid stroke="#CCCCCC"/>
              <XAxis
                dataKey="week"
                tick={{ fontSize: 10, fill: "#000" }}
                label={{
                  value: "нед",
                  position: "insideRight",
                  dy: -4,
                  dx: 30,
                  style: { fontSize: 10, fill: "#000" },
                }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#000" }}
                label={{
                  value: "единиц, товар, шт",
                  angle: 0,
                  position: "top",
                  dx: 70,
                  style: { textAnchor: "middle", fontSize: 10, fill: "#000" },
                }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                formatter={(value) => [`${value} шт`]}
                labelFormatter={(label) => `Неделя: ${label}`}
              />
              <Legend verticalAlign="top" align="right" height={13} wrapperStyle={{ fontSize: 10}} 
                formatter={(value: string) => <span style={{ color: '#000' }}>{value}</span>}/>
              <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <Line
                  type="linear"
                  dataKey="iphone"
                  name="apple iphone 17 pro max"
                  stroke="#7700FF"
                  strokeWidth={2}
                  dot={{ r: 0 }}
                />
                <Line
                  type="linear"
                  dataKey="nanotubes"
                  name="углеродные нанотрубки"
                  stroke="#FF5733"
                  strokeWidth={2}
                  dot={{ r: 0 }}
                />
                <Line
                  type="linear"
                  dataKey="tv"
                  name="телевизор xxxxxx"
                  stroke="#3F7BFF"
                  strokeWidth={2}
                  dot={{ r: 0 }}
                />
              </motion.g>
            </LineChart>
          </ResponsiveContainer>
        </div>
        <DialogClose />
      </DialogContent>
    </Dialog>
  );
}
