import { useState} from "react";
import { DataTable } from "../widgets/DataTable";
import { RobotActivityChart } from "@/components/widgets/RobotActivityChart";
import { Button } from "@/components/ui/button";
import AddLarge from '@atomaro/icons/24/action/AddLarge';
import ChevronDown from '@atomaro/icons/24/navigation/ChevronDown';
import { ForecastAI } from "../widgets/ForecastAI";
import { UserAvatar } from '../ui/UserAvatar.tsx'

function DashboardPage(){

    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
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
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        status: "Критично",
        },
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        status: "Критично",
        },
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        status: "Критично",
        },
        {
        time: "13:35:16",
        robot: "M-532",
        department: "Разгрузка",
        product: "Apple iPhone 17 Pro Max – 32400130",
        quantity: 36,
        status: "Критично",
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
            return "bg-[#0ACB5B]";
        case "Низкий остаток":
            return "bg-[#FDA610]";
        case "Критично":
            return "bg-[#FF4F12]";
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
        { header: "время проверки", accessor: "time" },
        { header: "id робота", accessor: "robot" },
        { header: "отдел склада", accessor: "department" },
        { header: "название товара и артикул", accessor: "product" },
        { header: "количество", accessor: "quantity", className: "font-semibold", align: "center" },
        {
            header: "статус",
            accessor: (row) => (
            <span
                className={`${getStatusColor(row.status)} text-black text-[12px] font-medium px-3 py-[3px] rounded-[8px]`}
            >
                {row.status}
            </span>
            ),
            align: "left",
        },
    ];


    return (
			<div className='flex bg-[#F4F4F5] min-h-screen'>
				<div className='flex flex-col flex-1 overflow-hidden ml-[60px]'>
					<header className='bg-white h-[60px] w-full flex items-center pl-[74px] pr-[10px] fixed top-0 left-0 z-[300]'>
						<span className='pagename-font'>Дашборд</span>

						<div className='ml-auto flex items-center gap-4'>
							<div className='relative'>
								<Button
									className='w-auto h-[38px] border-[#CCCCCC] border-[1px] rounded-[10px] font-400 text-[20px] text-[#7700FF] flex items-center justify-between px-4'
									onClick={() => setIsDropdownOpen(!isDropdownOpen)}
								>
									Склад WB-4325427
									<ChevronDown
										fill='#7700FF'
										className={`w-[20px] h-[20px] transition-transform duration-200 ${
											isDropdownOpen ? 'rotate-180' : ''
										}`}
									/>
								</Button>

								{isDropdownOpen && (
									<div className='absolute right-0 mt-1 w-auto bg-white border border-gray-300 rounded-[10px] shadow-lg z-50 text-[#7700FF] text-[20px]'>
										<button
											className='w-full text-left px-4 py-2 hover:bg-gray-100'
											onClick={() => console.log('Действие 1')}
										>
											Склад WB-4321245
										</button>
										<button
											className='w-full text-left px-4 py-2 hover:bg-gray-100'
											onClick={() => console.log('Действие 2')}
										>
											Склад WB-4321245353
										</button>
										<button
											className='w-full text-left px-4 py-2 hover:bg-gray-100'
											onClick={() => console.log('Действие 3')}
										>
											Склад WB-4321245123
										</button>
									</div>
								)}
							</div>
							<div className='flex items-center space-x-5'>
								<Button className='w-[319px] h-[38px] border-[#CCCCCC] border-[1px] rounded-[10px] text-[20px] text-[#7700FF] flex items-center justify-between px-4'>
									Добавить робота или товар
									<AddLarge fill='#7700FF' className='w-[20px] h-[20px]' />
								</Button>
								<UserAvatar />
							</div>
						</div>
					</header>
					<main className='flex-1 overflow-auto pt-[70px] pl-[10px] pr-[10px] pb-[10px]'>
						<div className='grid grid-cols-[2fr_3fr] gap-6 h-full'>
							<section className='bg-white rounded-[15px] p-[6px] flex flex-col'>
								<h2 className='font-semibold text-[18px] mb-2'>Карта склада</h2>
								<div className='flex-1 bg-[#F6F7F7] rounded-[10px]'></div>
							</section>
							<section className='grid grid-cols-2 gap-4 auto-rows-min'>
								<div className='bg-white rounded-[10px] p-[6px] pl-[12px] flex flex-col justify-between h-[102px]'>
									<h3 className='font-medium text-[18px] mb-1'>
										Критические остатки
									</h3>
									<div className='flex flex-col items-center justify-between space-y-[-8px] pb-4'>
										<p className='text-[28px] font-bold'>102</p>
										<p className='text-[10px] text-[#CCCCCC] font-light '>
											{' '}
											количество SKU{' '}
										</p>
									</div>
								</div>
								<div className='bg-white rounded-[10px] p-[6px] pl-[12px] flex flex-col justify-between h-[102px]'>
									<h3 className='font-medium text-[18px] mb-1'>
										Средний заряд батарей
									</h3>
									<div className='flex flex-col items-center justify-between space-y-[-8px] pb-4'>
										<p className='text-[28px] font-bold'>47%</p>
										<p className='text-[10px] text-[#CCCCCC] font-light '>
											{' '}
											среднее значение{' '}
										</p>
									</div>
								</div>
								<div className='bg-transparent grid grid-cols-[73%_calc(27%-1rem)] gap-4 col-span-2 w-full h-[200px]'>
									<div className='bg-white rounded-[10px] pt-[6px] pl-[10px] pr-[10px] pb-[10px]'>
										<h3 className='font-medium text-[18px] mb-1'>
											График активности роботов
										</h3>
										<div className='h-[150px] bg-white rounded-[10px] flex items-center justify-center'>
											<RobotActivityChart />
										</div>
									</div>
									<div className='flex flex-col gap-4'>
										<div className='bg-white rounded-[10px] h-[95px] flex flex-col p-[6px] pl-[12px]'>
											<h3 className='font-medium text-[18px]'>Роботы</h3>
											<div className='flex flex-col items-center justify-center space-y-[-8px]'>
												<span className='text-[30px] font-bold'>71/96</span>
												<p className='text-[10px] text-[#CCCCCC] font-[400]'>
													активных/всего
												</p>
											</div>
										</div>
										<div className='bg-white rounded-[10px] h-[95px] flex flex-col p-[6px] pl-[12px]'>
											<h3 className='font-medium text-[18px]'>
												Проверено за 24 ч
											</h3>
											<div className='flex flex-col items-center justify-center space-y-[-8px]'>
												<span className='text-[30px] font-bold'>1430</span>
												<p className='text-[10px] text-[#CCCCCC] font-[400]'>
													позиций
												</p>
											</div>
										</div>
									</div>
								</div>
								<div className='bg-white rounded-[15px] pl-[10px] pt-[6px] pr-[10px] pb-[10px] col-span-2 h-[334px]'>
									<h3 className='font-medium text-[18px]'>
										Последние сканирования
									</h3>
									<DataTable data={data} columns={columns} />
								</div>
								<div className='bg-white rounded-[15px] pl-[10px] pt-[6px] pr-[10px] pb-[10px] col-span-2'>
									<ForecastAI />
								</div>
							</section>
						</div>
					</main>
				</div>
			</div>
		)
};

export default DashboardPage;
