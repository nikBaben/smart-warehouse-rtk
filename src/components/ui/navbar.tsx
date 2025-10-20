import { React, useState } from "react";
import UploadCSV from "./UploadCSV";
import Logo from "/src/assets/logos/RTKlogo.svg";
import Home from "@atomaro/icons/24/action/Home";
import History from '@atomaro/icons/24/communication/History';
import MenuPlusBullets from "@atomaro/icons/24/navigation/MenuPlusBullets";
import Settings from '@atomaro/icons/24/action/Settings';
import Release from '@atomaro/icons/24/action/Release';
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ExitDialogue } from "./exitDialogue";

export function Navbar() {
	const [showExit, setShowExit] = useState(false);
  	const navigate = useNavigate();
  	return (
		<div className="w-[60px] h-screen bg-[#272F3D] flex flex-col items-center fixed top-0 left-0 z-[1000]">
			<div className="w-[25px] h-[60px] flex flex-col items-center justify-center">
				<a href="#/">
					<img src={Logo} alt="RTK" className="h-[40px] w-auto object-contain" />
				</a>
			</div>

			<div className="absolute top-[60px] left-1/2 -translate-x-1/2 w-[60px] border-b-[1px] border-[#5A606D]" />

			<div className="flex flex-col items-center w-[30px] h-[250px] justify-center gap-[30px]">
				<nav className="flex flex-col gap-[30px] items-center">
					<NavItem icon={Home} label="Главная" to="/" />
					<NavItem icon={History} label="Карта" to="/history" />
					<NavItem icon={MenuPlusBullets} label="Меню" to="/list" />
					<UploadCSV/>
				</nav>
			</div>

			<div className="flex flex-col items-center absolute bottom-[20.15px]">
				<nav className="flex gap-[26px] flex-col">
					<NavItem icon={Settings} label="Настройки" to="/settings" />
					<button
					onClick={() => setShowExit(true)}
					title="Выход"
					className="transition-transform hover:scale-110"
					>
					<Release
						fill="#9CA3AF"
						className="hover:fill-white transition-colors duration-200 w-[30px] h-auto"
					/>
					</button>
				</nav>
        	</div>
			{showExit && (
				<ExitDialogue
				onStay={() => setShowExit(false)}
				onExit={() => {setShowExit(false); navigate("/auth"); }}
				/>
			)}
		</div>
	);
}

const NavItem = ({
  icon: Icon,
  label,
  to,
}: {
  icon: React.ElementType;
  label: string;
  to: string;
}) => {
  const location = useLocation();
  const active = location.pathname === to;
  const fillColor = active ? "#FFFFFF" : "#9CA3AF";

  return (
    <Link to={to} title={label} className="transition-transform">
      <Icon
        fill={fillColor}
        className="hover:fill-white transition-colors duration-200 w-[30px] h-auto"
      />
    </Link>
  );
};
