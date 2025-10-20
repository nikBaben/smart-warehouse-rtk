import { React, useState} from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import CheckLarge from "@atomaro/icons/24/navigation/CheckLarge";
import CloseLarge from "@atomaro/icons/24/navigation/CloseLarge";
import { Checkbox } from "@/components/ui/checkbox";
import SelectableButtons from "@/components/widgets/SelectableButtons";

function HistoryPage(){
    const zones = ["разгрузка", "погрузка", "заморозка", "зона особых товаров"];
    const categories = ["бытовая техника и электроника", "смартфоны", "комплектующие для ПК", "сетевое оборудование", "драгоценные металлы", "редкие дорогостоящие вещества", "оружие", "другое"]

    return (
        <div className="flex bg-[#F4F4F5] min-h-screen">
            <div className="flex flex-col flex-1 overflow-hidden ml-[60px]">
                <header className="bg-white h-[60px] w-full flex items-center px-[74px] fixed top-0 left-0 z-[300]">
                    <span className="page-name">Исторические данные</span>
                </header>
                <main className="flex-1 pt-[70px] pl-[10px] pr-[10px] pb-[10px]">
                    <div className="h-[583px] w-[218px]">
                        <h2 className="font-medium text-[20px] "> Фильтры</h2>
                        <div className="h-[552px] w-[218px] bg-white rounded-[15px]">
                            <div className="p-[10px] flex flex-col w-[198px] gap-[15px]">
                                <div>
                                    <span className="text-[14px] font-medium"> Поиск </span>
                                    <Input placeholder = "артикул или название товара" className="h-[18px] w-[198px] border-none shadow-none bg-[#F2F3F4] placeholder:font-medium placeholder:text-[10px] !text-[10px] !text-[#000000]"></Input>
                                </div>
                                <div className="h-[85px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Выбор периода </span>
                                    <div className="h-[39px] w-[198px]">
                                        <div className="flex">
                                            
                                        </div>
                                    </div>
                                </div>
                                <div className="h-[99px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Зоны склада </span>
                                    <SelectableButtons params={zones}/>
                                </div>
                                <div className="h-[176px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Категории товаров </span>
                                    <SelectableButtons params={categories}/>
                                </div>
                                <div className="h-[53px] w-[198px]">
                                    <span className="text-[14px] font-medium"> Статус </span>
                                    <div className="h-[35px]  p-[5px] bg-[#F2F3F4] gap-[0px] rounded-[5px] flex-col items-center">
                                        <div className="flex gap-[2px]  items-center">
                                            <Checkbox className="history-checkbox"/> 
                                            <span className="text-[#000000] text-[10px]">
                                                все
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <div className="flex gap-[2px]  items-center">
                                                <Checkbox className="history-checkbox"/> 
                                                <span className="text-[#000000] text-[10px]">
                                                    ок
                                                </span>
                                            </div>
                                            <div className="flex gap-[2px] items-center">
                                                <Checkbox className="history-checkbox"/> 
                                                <span className="text-[#000000] text-[10px]">
                                                    низкий остаток
                                                </span>                                         
                                            </div>
                                            <div className="flex gap-[2px]  items-center">
                                                <Checkbox className="history-checkbox"/> 
                                                <span className="text-[#000000] text-[10px]">
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
                </main>
            </div>
        </div>
    )
}
export default HistoryPage;