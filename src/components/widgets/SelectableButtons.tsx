import { useState } from "react";
import { Check } from "lucide-react";

import { Button } from "../ui/button";

interface SelectableButtonsProps {
  params: string[];
}

const SelectableButtons: React.FC<SelectableButtonsProps> = ({ params }) => {
  const [selectedParams, setSelectedParams] = useState<string[]>([]);

  const toggleZone = (param: string) => {
    if (selectedParams.includes(param)) {
      setSelectedParams(selectedParams.filter((p) => p !== param));
    } else {
      setSelectedParams([...selectedParams, param]);
    }
  };

  return (
    <div className="rounded-[5px] bg-[#F2F3F4] flex flex-col gap-[2px]">
      {params.map((param, index) => {
        const isSelected = selectedParams.includes(param);
        return (
          <Button
            key={index}
            onClick={() => toggleZone(param)}
            className={`flex items-center w-[198px] h-[18px] text-[10px] font-medium text-black justify-between rounded-[5px] shadow-none p-[2px] ${
              isSelected ? "border border-purple-600" : "border border-transparent"
            }`}
          >
            {param}
            {isSelected && <Check className="w-3 h-3 mr-1 text-black" />}
          </Button>
        );
      })}
    </div>
  );
};

export default SelectableButtons;
