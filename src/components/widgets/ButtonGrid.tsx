import { useState } from "react";
import { Button } from "../ui/button"; // импортируй свой Button

export function ButtonGrid() {
  const [activeButton, setActiveButton] = useState<number | null>(null);

  const buttons = ["сегодня", "вчера", "неделя", "месяц"];

  return (
    <div className="grid grid-cols-2 gap-x-[6px] gap-y-[3px]">
      {buttons.map((label, index) => (
        <Button
          key={label}
          onClick={() => setActiveButton(index)}
          className={`h-[24px] w-[96px] text-[12px] font-medium cursor-pointer
                      ${activeButton === index ? "border-[1px] border-[#7700FF]" : "border-none"} 
                      bg-[#F2F3F4] text-black shadow-none`}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
