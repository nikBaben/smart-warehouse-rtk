import { React } from "react";
import { Navbar } from "@/components/ui/navbar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import { Badge } from "@/components/ui/badge";

const DashboardPage: React.FC = () => {
    const data = [
        {
        time: "14:00:00",
        robot: "M-532",
        department: "Разгрузка",
        product: "Ящик деревянный – 00000",
        quantity: 36,
        status: "Низкий остаток",
        },
        {
        time: "13:56:29",
        robot: "E-429",
        department: "Разгрузка",
        product: "Фигурка коллекционная – 32400130",
        quantity: 36,
        status: "OK",
        },
        {
        time: "13:41:21",
        robot: "M-532",
        department: "Разгрузка",
        product: "Монитор XXXXXXXXX – 00000",
        quantity: 36,
        status: "Низкий остаток",
        },
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        status: "Критично",
        },
    ];

    const getStatusColor = (status: string) => {
        switch (status) {
        case "OK":
            return "bg-green-500 hover:bg-green-600";
        case "Низкий остаток":
            return "bg-yellow-500 hover:bg-yellow-600";
        case "Критично":
            return "bg-red-500 hover:bg-red-600";
        default:
            return "bg-gray-400";
        }
    };

    return (
        <div className="flex bg-[#F4F4F5] min-h-screen">
            <Navbar />
            <div className="flex flex-col flex-1 overflow-hidden">
                <header className="bg-white h-[60px] flex items-center px-[74px] shadow-sm z-10">
                    <span className="font-bold text-black text-[24px]">Дашборд</span>
                </header>
                <main className="flex-1 p-6 overflow-auto">
                    <div className="grid grid-cols-[2fr_3fr] gap-6 h-full">
                        <section className="bg-white rounded-[15px] p-4 flex flex-col">
                            <h2 className="font-semibold text-[18px] mb-2">Карта склада</h2>
                            <div className="flex-1 bg-[#F6F7F7] rounded-[10px]"></div>
                        </section>
                        <section className="grid grid-cols-2 gap-4 auto-rows-min">
                            <div className="bg-white rounded-[15px] p-4 flex flex-col justify-between">
                                <h3 className="font-medium text-[18px] mb-1">Критические остатки</h3>
                                <div className="flex flex-col items-center justify-between">
                                    <p className="text-[28px] font-bold">102</p>
                                    <p className="text-[10px] text-[#CCCCCC] font-light "> количество SKU </p>
                                </div>
                            </div>
                            <div className="bg-white rounded-[15px] p-4 flex flex-col justify-between">
                                <h3 className="font-medium text-[18px] mb-1">Средний заряд батарей</h3>
                                <div className="flex flex-col items-center justify-between">
                                    <p className="text-[28px] font-bold">47%</p>
                                    <p className="text-[10px] text-[#CCCCCC] font-light "> среднее значение </p>
                                </div>
                            </div>
                            <div className="bg-transparent grid grid-cols-[78%_calc(22%-1rem)] gap-4 col-span-2 w-full">
                                <div className="bg-white rounded-[15px] p-4">
                                    <h3 className="font-medium text-[18px] mb-1">График активности роботов</h3>
                                    <div className="h-[150px] bg-[#F6F7F7] rounded-[10px]"></div>
                                </div>
                                <div className="flex flex-col gap-4">
                                    <div className="bg-white rounded-[15px] p-4 h-[95px] flex flex-col items-center justify-between">
                                        <h3 className="font-medium text-[16px]">Роботы</h3>
                                        <span className="text-[24px] font-bold">71/96</span>
                                    </div>
                                    <div className="bg-white rounded-[15px] p-4 h-[95px] flex flex-col  items-center justify-between">
                                        <h3 className="font-medium text-[16px]">Проверено за 24 ч</h3>
                                        <span className="text-[24px] font-bold">1430</span>
                                    </div>
                                </div>
                            </div>
                            <div className="bg-white rounded-[15px] p-5 col-span-2 shadow-sm">
                                <h3 className="font-semibold text-[16px] mb-3">Последние сканирования</h3>
                                <div className="overflow-hidden rounded-[5px] bg-[#FFFFFF]">
                                    <Table className="border-separate border-spacing-y-[5px] border-0 [&_*]:border-0 w-full">
                                    <TableHeader  className="text-[10px]">
                                        <TableRow className="bg-[#FFFFFF] text-black">
                                        <TableHead className="font-semibold">время проверки</TableHead>
                                        <TableHead className="font-semibold">id робота</TableHead>
                                        <TableHead className="font-semibold">отдел склада</TableHead>
                                        <TableHead className="font-semibold">название товара и артикул</TableHead>
                                        <TableHead className="text-center font-semibold">количество</TableHead>
                                        <TableHead className="text-center font-semibold">статус</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody className="[&_tr]:h-[30px]">
                                        {data.map((item, i) => (
                                        <TableRow
                                            key={i}
                                            className="bg-[#F6F7F7] row-height"
                                        >
                                            <TableCell className="py-3">{item.time}</TableCell>
                                            <TableCell>{item.robot}</TableCell>
                                            <TableCell>{item.department}</TableCell>
                                            <TableCell>{item.product}</TableCell>
                                            <TableCell className="text-center font-semibold">{item.quantity}</TableCell>
                                            <TableCell className="text-center">
                                            <span
                                                className={`${getStatusColor(
                                                item.status
                                                )} text-white text-[12px] font-medium px-3 py-[3px] rounded-[8px]`}
                                            >
                                                {item.status}
                                            </span>
                                            </TableCell>
                                        </TableRow>
                                        ))}
                                    </TableBody>
                                    </Table>
                                </div>
                            </div>
                            <div className="bg-white rounded-[15px] p-4 col-span-2">
                                <h3 className="font-semibold text-[16px] mb-2">Прогноз ИИ на следующие 7 дней</h3>
                                <div className="flex flex-col gap-2">
                                    <div className="flex justify-between p-2 bg-[#F6F7F7] rounded-[10px]">
                                        <span>Apple iPhone 17 Pro Max</span>
                                        <span>88%</span>
                                    </div>
                                </div>
                            </div>
                        </section>
                    </div>
                </main>
            </div>
        </div>
    );
};

export default DashboardPage;
