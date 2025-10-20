function HistoryPage(){
    return (
        <div className="flex bg-[#F4F4F5] min-h-screen">
            <div className="flex flex-col flex-1 overflow-hidden ml-[60px]">
                <header className="bg-white h-[60px] w-full flex items-center px-[74px] fixed top-0 left-0 z-[300]">
                    <span className="font-bold text-black text-[24px]">Параметры и уведомления</span>
                </header>
                <main className="flex-1 p-4"></main>
            </div>
        </div>
    )
}
export default HistoryPage;