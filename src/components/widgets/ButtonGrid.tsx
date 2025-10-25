import type { Dispatch, SetStateAction } from "react";
import { Button } from "../ui/button";

interface ButtonGridProps {
  selected: string[];
  onChange: Dispatch<SetStateAction<string[]>>;
}

export function ButtonGrid({ selected, onChange }: ButtonGridProps) {
  const buttons = ["сегодня", "вчера", "неделя", "месяц"];

  const toggleButton = (label: string) => {
    onChange(prev =>
      prev.includes(label)
        ? prev.filter(l => l !== label)
        : [...prev, label]
    );
  };

  return (
    <div className="grid grid-cols-2 gap-x-[6px] gap-y-[3px]">
      {buttons.map(label => (
        <Button
          key={label}
          onClick={() => toggleButton(label)}
          className={`h-[24px] w-[96px] text-[12px] font-medium cursor-pointer
                      ${selected.includes(label) ? "border-[1px] border-[#7700FF]" : "border-none"} 
                      bg-[#F2F3F4] text-black shadow-none`}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
