import React from "react";
import Logo from "/src/assets/logos/RTKlogo.svg";
import Home from "@atomaro/icons/24/action/Home";
import Pin from "@atomaro/icons/24/navigation/Pin";
import MenuPlusBullets from "@atomaro/icons/24/navigation/MenuPlusBullets";
import Settings from '@atomaro/icons/24/action/Settings';
import Release from '@atomaro/icons/24/action/Release';

export function Navbar() {
  return (
    <div className="w-[60px] h-screen bg-[#272F3D] flex flex-col items-center relative sticky">
      <div className="w-[25px] h-[60px] flex flex-col items-center justify-center">
        <a href="#/">
          <img src={Logo} alt="RTK" className="h-[40px] w-auto object-contain" />
        </a>
      </div>
      <div
        className="absolute top-[60px] left-1/2 -translate-x-1/2 w-[60px] border-b-[1px] border-[#5A606D]"
      />
      <div className="flex flex-col items-center w-[30px] h-[180px] justify-center gap-[30px]">
        <nav className="flex flex-col gap-[30px] items-center">
          <NavItem icon={Home} label="Главная" />
          <NavItem icon={Pin} label="Карта" />
          <NavItem icon={MenuPlusBullets} label="Меню" />
        </nav>
      </div>
      <div className="flex flex-col items-center absolute bottom-[20.15px]">
        <nav className="flex gap-[26px] flex-col">
          <NavItem icon= {Settings} label="Настройки"/>
          <NavItem icon= {Release} label="Выход"/>
        </nav>
      </div>
    </div>
  );
}

const NavItem = ({
  icon: Icon,
  label,
  active = false,
}: {
  icon: React.ElementType;
  label: string;
  active?: boolean;
}) => {
  const fillColor = active ? "#FFFFFF" : "#9CA3AF"; // gray-400 → white при активном

  return (
    <button
      className="transition-colors duration-200 hover:scale-110"
      title={label}
    >
      <Icon fill={fillColor} className="hover:fill-white transition-colors duration-200 w-[30px] h-auto" />
    </button>
  );
};
