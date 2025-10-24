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
        time: "25.10.2025 - 13:35",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max",
        quantity: 36,
        discrepancy: -7,
        status: "Критично",
        category: "смартфоны"
        },  
        {
        time: "24.10.2025 - 12:23",
        robot: "M-228",
        department: "Разгрузка",
        product: "Золото",
        quantity: 36,
        discrepancy: 6,
        status: "OK",
        category: "драгоценные металлы"
        }, 
        {
        time: "07.08.2025 - 12:23",
        robot: "M-228",
        department: "Разгрузка",
        product: "Золото",
        quantity: 36,
        discrepancy: 6,
        status: "OK",
        category: "драгоценные металлы"
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
        sortable?: boolean;
        sortKey?: keyof T;
    };

    const columns: Column<typeof data[0]>[] = [
        { header: "дата и время проверки", accessor: "time", sortable: true },
        { header: "id робота", accessor: "robot", sortable: true},
        { header: "зона склада", accessor: "department", sortable: true },
        { header: "название", accessor: "product", sortable: true },
        { header: "количество ожидаемое/фактическое", accessor: "quantity", sortable: true },
        { header: "расхождение (+/-)", accessor: "discrepancy", sortable: true},
        {
            header: "статус",
            accessor: (row) => (
            <span
                className={`${getStatusColor(row.status)} text-black text-[10px] font-light rounded-[5px] px-[4px] py-[2px]`}
            >
                {row.status}
            </span>
            ),
            align: "left", sortable: true, sortKey: "status"
        },
    ];

    {/*Наверное так удобнее будет*/}
    const zones = ["разгрузка", "погрузка", "заморозка", "зона особых товаров"];
    const categories = ["бытовая техника и электроника", "смартфоны", "комплектующие для ПК", "сетевое оборудование", "драгоценные металлы", "редкие дорогостоящие вещества", "оружие", "другое"]

    const [search, setSearch] = useState("");
    const [selectedZone, setSelectedZone] = useState<string[]>([]);
    const [selectedCategory, setSelectedCategory] = useState<string[]>([]);
    const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
    const [startDate, setStartDate] = useState<Date | undefined>();
    const [endDate, setEndDate] = useState<Date | undefined>();
    const [filteredData, setFilteredData] = useState(data);
    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);

    const applyFilters = () => {
        const now = new Date();
        const result = data.filter((item) => {
            const matchesSearch =
                search.trim() === "" ||
                item.product.toLowerCase().includes(search.toLowerCase());

            const matchesZone =
                selectedZone.length === 0 ||
                selectedZone.some(zone => item.department.toLowerCase() === zone.toLowerCase());

            const matchesCategory =
                selectedCategory.length === 0 ||
                selectedCategory.some(cat => item.category?.toLowerCase() === cat.toLowerCase());

            const matchesStatus =
                selectedStatuses.length === 0 ||
                selectedStatuses.includes(item.status.toLowerCase());
            
            const [day, month, year] = item.time.split(" - ")[0].split(".");
            const itemDate = new Date(+year, +month - 1, +day);
            let matchesPeriod = selectedPeriods.length === 0;
            selectedPeriods.forEach(period => {
                switch (period) {
                    case "сегодня": {
                        const today = new Date();
                        matchesPeriod ||= itemDate.toDateString() === today.toDateString();
                        break;
                    }
                    case "вчера": {
                        const yesterday = new Date();
                        yesterday.setDate(yesterday.getDate() - 1);
                        matchesPeriod ||= itemDate.toDateString() === yesterday.toDateString();
                        break;
                    }
                    case "неделя": {
                        const weekAgo = new Date();
                        weekAgo.setDate(now.getDate() - 7);
                        matchesPeriod ||= itemDate >= weekAgo && itemDate <= now;
                        break;
                    }
                    case "месяц": {
                        const monthAgo = new Date();
                        monthAgo.setMonth(now.getMonth() - 1);
                        matchesPeriod ||= itemDate >= monthAgo && itemDate <= now;
                        break;
                    }
                }
            });
            const matchesDate =
                (!startDate || itemDate >= startDate) &&
                (!endDate || itemDate <= endDate);
            console.log(selectedStatuses);
            return matchesSearch && matchesZone && matchesStatus && matchesCategory && matchesDate && matchesPeriod;
        });

        setFilteredData(result);
    };

    const resetFilters = () => {
        setSearch("");
        setSelectedZone([]);
        setSelectedCategory([]);
        setSelectedStatuses([]);
        setStartDate(undefined)
        setEndDate(undefined)
        setFilteredData(data);
    };

    const toggleStatus = (status: string) => {
        setSelectedStatuses((prev) =>
        prev.includes(status)
            ? prev.filter((s) => s !== status)
            : [...prev, status]
        );
    };

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
                                    <Input value = {search} onChange={(e) => setSearch(e.target.value)} placeholder = "артикул или название товара" className="h-[24px] w-[198px] border-none shadow-none bg-[#F2F3F4] placeholder:font-medium placeholder:text-[12px] !text-[12px] !text-[#000000] px-[5px]"></Input>
                                </div>
                                <div className="h-[103px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Выбор периода </span>
                                    <div className="h-[82px] w-[198px]">
                                        <div className="flex flex-col gap-[7px]">
                                            <div>
                                                {/*Нужно пофиксить DatePicker, с ним прям беды какие-то*/}
                                                <DatePicker 
                                                startDate={startDate}
                                                endDate={endDate}
                                                onChange={(start, end) => {
                                                    setStartDate(start);
                                                    setEndDate(end);
                                                    setSelectedPeriods([]);
                                                }}
                                                />

                                            </div> 
                                            <div>
                                                <ButtonGrid
                                                selected={selectedPeriods}
                                                onChange={(periods) => {
                                                    setSelectedPeriods(periods);
                                                    if (periods.length > 0) {
                                                    setStartDate(undefined);
                                                    setEndDate(undefined);
                                                    }
                                                }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="h-[120px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Зоны склада </span>
                                    <SelectableButtons params={zones} onSelect={setSelectedZone} selected={selectedZone} multiple/>
                                </div>
                                <div className="h-[231px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Категории товаров </span>
                                    <SelectableButtons params={categories} onSelect={setSelectedCategory} selected={selectedCategory} multiple/>
                                </div>
                                <div className="h-[53px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Статус </span>
                                    <div className="h-[35px] pl-[5px] bg-[#F2F3F4] gap-[5px] rounded-[5px] flex-col items-center">
                                        <div className="flex gap-[5px] items-center">
                                            <div className="flex gap-[2px] items-center">
                                                <Checkbox 
                                                    checked={selectedStatuses.length === 0}  
                                                    onCheckedChange={() => setSelectedStatuses([])}
                                                    className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    все
                                                </span>
                                            </div>
                                            <div className="flex gap-[2px] items-center">
                                                <Checkbox 
                                                checked={selectedStatuses.includes("ok")}
                                                onCheckedChange={() => toggleStatus("ok")}
                                                className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    ок
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-[5px]">
                                            <div className="flex gap-[2px] items-center">
                                                <Checkbox 
                                                checked={selectedStatuses.includes("низкий остаток")} 
                                                onCheckedChange={() => toggleStatus("низкий остаток")}
                                                className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    низкий остаток
                                                </span>                                         
                                            </div>
                                            <div className="flex gap-[2px]  items-center">
                                                <Checkbox 
                                                checked={selectedStatuses.includes("критично")} 
                                                onCheckedChange={() => toggleStatus("критично")}
                                                className="history-checkbox cursor-pointer"/> 
                                                <span className="text-[#000000] text-[12px]">
                                                    критично
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex h-[18px] w-[198px] gap-[4px]">
                                    <Button onClick={resetFilters} className="bg-[#FF4F12] text-[10px] text-white h-[18px] w-[97px]">
                                        <CloseLarge fill="#FFFFFF"className="w-[7px] h-[7px]"/>
                                        Cбросить
                                    </Button>
                                    <Button onClick = {applyFilters} className="bg-[#7700FF] text-[10px] text-white h-[18px] w-[97px]">
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
                                <DataTableHistory data={filteredData} columns={columns} />
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