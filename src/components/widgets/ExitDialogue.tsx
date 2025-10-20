import React from "react";
import { Button } from "../ui/button";
import CheckLarge from "@atomaro/icons/24/navigation/CheckLarge";
import CloseLarge from "@atomaro/icons/24/navigation/CloseLarge";

export const ExitDialogue: React.FC<{ onStay: () => void; onExit: () => void }> = ({
  onStay,
  onExit,
}) => {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/60 z-[600]">
      <div className="bg-[#EFEFF0] h-[116px] w-[558px] rounded-[15px] p-[20px] flex flex-col justify-between">
        <span className="text-[24px] font-medium">Вы точно хотите выйти?</span>
        <div className="flex gap-[15px] items-center justify-center">
          <Button
            className="bg-[#7700FF] text-white text-[18px] flex-1 flex items-center gap-[8px] rounded-[10px]"
            onClick={onStay}
          >
            <CloseLarge fill="white"/>
            Остаться
          </Button>
          <Button
            className="bg-[#FF2626] text-white text-[18px] flex-1 flex items-center gap-[8px] rounded-[10px]"
            onClick={onExit}
          >
            <CheckLarge fill="white"/>
            Выйти
          </Button>
        </div>
      </div>
    </div>
  );
};