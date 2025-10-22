import { useState} from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import CheckLarge from "@atomaro/icons/24/navigation/CheckLarge";
import CloseLarge from "@atomaro/icons/24/navigation/CloseLarge";
import { Checkbox } from "@/components/ui/checkbox";
import SelectableButtons from "@/components/widgets/SelectableButtons";
import { UserAvatar } from '../ui/UserAvatar.tsx'

import { DatePicker } from "../widgets/DatePicker";
import { ButtonGrid } from "../widgets/ButtonGrid";
import { DataTableHistory } from "../widgets/DataTableHistory";

import StatisticsLine from '@atomaro/icons/24/business/StatisticsLine';
import Upload from '@atomaro/icons/24/action/Upload';


function HistoryPage(){
        const data = [
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        },  
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
                {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        },  
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
                {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        },  
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
                {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        },  
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
                {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        },  
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
                {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        },  
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "OK",
        }, 
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        discrepancy: -7,
        status: "Низкий остаток",
        }, 
    ];

    const getStatusColor = (status: string) => {
        switch (status) {
        case "OK":
            return "bg-[#0ACB5B]";
        case "Низкий остаток":
            return "bg-[#FDA610]";
        case "Критично":
            return "bg-[#FF2626]";
        default:
            return "bg-gray-400";
        }
    };

    type Column<T> = {
        header: string;
        accessor: keyof T | ((row: T) => React.ReactNode);
        className?: string;
        align?: "left" | "center" | "right";
    };

    const columns: Column<typeof data[0]>[] = [
        { header: "дата и время проверки", accessor: "time" },
        { header: "id робота", accessor: "robot" },
        { header: "зона склада", accessor: "department" },
        { header: "название", accessor: "product" },
        { header: "количество ожидаемое/фактическое", accessor: "quantity" },
        { header: "расхождение (+/-)", accessor: "discrepancy" },
        {
            header: "статус",
            accessor: (row) => (
            <span
                className={`${getStatusColor(row.status)} text-black text-[10px] font-light rounded-[5px] px-[4px] py-[2px]`}
            >
                {row.status}
            </span>
            ),
            align: "left",
        },
    ];

    {/*Наверное так удобнее будет*/}
    const zones = ["разгрузка", "погрузка", "заморозка", "зона особых товаров"];
    const categories = ["бытовая техника и электроника", "смартфоны", "комплектующие для ПК", "сетевое оборудование", "драгоценные металлы", "редкие дорогостоящие вещества", "оружие", "другое"]

    return (
        <div className="flex bg-[#F4F4F5] min-h-screen">
            <div className="flex flex-col flex-1 overflow-hidden ml-[60px]">
                <header className='bg-white justify-between flex items-center h-[60px] px-[14px] z-10'>
                    <span className='pagename-font'>Исторические данные</span>
                    <div className='flex items-center space-x-5'>
                        <UserAvatar />
                    </div>
                </header>
                <main className="flex pt-[10px] pl-[10px] pr-[10px] pb-[10px]">
                    <div className="h-[662px] w-[218px]">
                        <h2 className="font-medium text-[20px] "> Фильтры</h2>
                        <div className="h-[662px] w-[218px] bg-white rounded-[15px]">
                            <div className="p-[10px] flex flex-col w-[199px] gap-[15px]">
                                <div className="h-[42px]">
                                    <span className="text-[14px] font-medium"> Поиск </span>
                                    <Input placeholder = "артикул или название товара" className="h-[24px] w-[198px] border-none shadow-none bg-[#F2F3F4] placeholder:font-medium placeholder:text-[12px] !text-[12px] !text-[#000000] px-[5px]"></Input>
                                </div>
                                <div className="h-[103px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Выбор периода </span>
                                    <div className="h-[82px] w-[198px]">
                                        <div className="flex flex-col gap-[7px]">
                                            <div>
                                                {/*Нужно пофиксить DatePicker, с ним прям беды какие-то*/}
                                                <DatePicker/>
                                            </div> 
                                            <div>
                                                <ButtonGrid/>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="h-[120px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Зоны склада </span>
                                    <SelectableButtons params={zones}/>
                                </div>
                                <div className="h-[231px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Категории товаров </span>
                                    <SelectableButtons params={categories}/>
                                </div>
                                <div className="h-[53px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Статус </span>
                                    <div className="h-[35px] pl-[5px] bg-[#F2F3F4] gap-[5px] rounded-[5px] flex-col items-center">
                                        <div className="flex gap-[5px] items-center">
                                            <div className="flex gap-[2px] items-center">
                                                <Checkbox className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    все
                                                </span>
                                            </div>
                                            <div className="flex gap-[2px] items-center">
                                                <Checkbox className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    ок
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-[5px]">
                                            <div className="flex gap-[2px] items-center">
                                                <Checkbox className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    низкий остаток
                                                </span>                                         
                                            </div>
                                            <div className="flex gap-[2px]  items-center">
                                                <Checkbox className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    критично
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex h-[18px] w-[198px] gap-[4px]">
                                    <Button className="bg-[#FF4F12] text-[10px] text-white h-[18px] w-[97px]">
                                        <CloseLarge fill="#FFFFFF"className="w-[7px] h-[7px]"/>
                                        Cбросить
                                    </Button>
                                    <Button className="bg-[#7700FF] text-[10px] text-white h-[18px] w-[97px]">
                                        <CheckLarge fill="#FFFFFF"className="w-[7px] h-[7px]"/>
                                        Применить
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-col pl-[10px] w-full  gap-[5px]">
                        {/*Ультра заглушка, потом что-то нормальное напишу*/}
                        <div className="h-[77px]">
                            <h2 className="font-medium text-[20px]">Сводная статистика</h2>
                            <div className="h-[46px] bg-white rounded-[15px] flex items-center justify-between p-[10px]">
                                <span className="text-[14px] font-light">всего проверок за период: 12375</span>
                                <span className="text-[14px] font-light">уникальных товаров: 56</span>
                                <span className="text-[14px] font-light">выявлено расхождений: 21</span>
                                <span className="text-[14px] font-light">среднее время инвентаризации: 10 мин</span>
                            </div>
                        </div>
                        <div>
                            <h2 className="font-medium text-[20px]">Историческая таблица</h2>
                            <div className="h-[751px] bg-white rounded-[15px] pl-[10px] pr-[10px]">
                                <DataTableHistory data={data} columns={columns} />
                            </div>
                        </div>
                        <div className="flex items-center justify-end gap-[10px] pt-[10px]">
                            <div className="flex gap-[5px]">
                                <Button className="h-[30px] w-[187px] text-[12px] text-[#7700FF] bg-[#F7F0FF] border-[#7700FF] border-[1px] rounded-[10px] font-medium">
                                    <Upload fill="#7700FF" className="h-[8px] w-[8px]"/>
                                    Экспорт в Excel
                                </Button>
                                <Button className="h-[30px] w-[187px] text-[12px] text-[#7700FF] bg-[#F7F0FF] border-[#7700FF] border-[1px] rounded-[10px] font-medium">
                                    <Upload fill="#7700FF" className="h-[8px] w-[8px]"/>
                                    Экспорт в PDF
                                </Button>
                            </div>
                            <Button className="h-[30px] w-[187px] text-[12px] text-white bg-[#7700FF] rounded-[10px] font-medium">
                                <StatisticsLine fill="white" className="h-[6px] w-[11px]"/>
                                Построить график
                            </Button>
                        </div>
                    </div>
                </main>
            </div>
        </div>
    )
}
export default HistoryPage;