import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";

import { Header } from "@/components/ui/header";
import { Footer } from "@/components/ui/footer";
  
{/*вообще временная фигня, потом на нормальную маску поменяю*/}
function AuthPage(){
  const [role, setRole] = useState<"user" | "admin">("user");
  const [login, setLogin] = React.useState("");

  const isPhoneInput = (value: string) => /^[\d+]/.test(value);

  const handleLoginChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;

    if (isPhoneInput(value)) {
      const digits = value.replace(/\D/g, "").slice(0, 11);
      const formatted = digits.replace(
        /(\d)(\d{0,3})(\d{0,3})(\d{0,2})(\d{0,2})/,
        (match, p1, p2, p3, p4, p5) => {
          let result = "+";
          result += p1 || "";
          if (p2) result += " (" + p2;
          if (p2 && p2.length === 3) result += ")";
          if (p3) result += " " + p3;
          if (p4) result += "-" + p4;
          if (p5) result += "-" + p5;
          return result;
        }
      );
      setLogin(formatted);
    } else {
      setLogin(value);
    }
};

  const [password, setPassword] = useState("");

  return (
    <div className="min-h-screen flex flex-col bg-[#F4F4F5] text-gray-900 font-rostelecom">
      <Header />
      <main className="flex-1 flex flex-col items-center justify-center p-4 relative">
        <div className="flex flex-col gap-[20px]">
          <div className="w-[403px] h-[624px] bg-white rounded-[15px] overflow-hidden max-w-md p-8 flex flex-col items-center">
            <div className="w-[365px] h-[68px] flex flex-col gap-[25px]">
              <h1 className="text-2xl font-bold flex flex-col items-center justify-center">Войти на склад</h1>
              <div className="flex items-center justify-center gap-5">
                <Button
                  className={`w-[174px] h-[50px] px-[56px] py-[5px] rounded-[10px] text-[18px] flex items-center justify-center hover:opacity-90 shadow-none ${
                    role === "user"
                      ? "bg-[#7700FF] text-white"
                      : "bg-[#F7F0FF] text-[#7700FF] hover:bg-purple-200"
                  }`}
                  onClick={() => setRole("user")}
                >
                  Пользователь
                </Button>

                <Button
                  className={`w-[174px] h-[50px] px-[56px] py-[5px] rounded-[10px] text-[18px] flex items-center justify-center hover:opacity-90 shadow-none ${
                    role === "admin"
                      ? "bg-[#7700FF] text-white"
                      : "bg-[#F7F0FF] text-[#7700FF] hover:bg-purple-200"
                  }`}
                  onClick={() => setRole("admin")}
                >
                  Админ
                </Button>
              </div>
              <div className="flex flex-col items-center justify-center">
                <Input
                  placeholder="Телефон, почта или логин"
                  value={login}
                  onChange={handleLoginChange}
                  className="w-[365px] h-[68px] rounded-[10px] border-none bg-[#F2F3F4] placeholder-[#A1A1AA] placeholder:font-medium placeholder:text-[18px] placeholder:leading-[24px] shadow-none !text-[18px] !leading-[24px] !text-[#000000] !font-medium"
                />
              </div>
              <div className="flex flex-col gap-[20px]">
                <div className="flex flex-col items-center justify-center">
                  <Input
                    type="password"
                    placeholder="Пароль"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-[365px] h-[68px] rounded-[10px] border-none bg-[#F2F3F4] placeholder-[#A1A1AA] placeholder:font-medium placeholder:text-[18px] placeholder:leading-[24px] shadow-none !text-[18px] !leading-[24px] !text-[#000000] !font-medium"
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox className={`
                        shadow-none
                        peer
                        w-5 h-5 border-1 rounded-[5px]
                        bg-[#F2F3F4] border-[#F2F3F4]
                        data-[state=checked]:bg-[#F2F3F4]
                        data-[state=checked]:text-[#7700FF]
                        data-[state=checked]:border-[#7700FF]
                        transition-colors duration-200
                        flex items-center justify-center`}/> 
                  <span className="text-[#000000] text-[16px] leading-[24px]">
                    Запомнить меня
                  </span>
                </div>
              </div>
              <div className="flex flex-col items-center justify-center">
                <Button
                  disabled={!login || !password}
                  className={`w-[365px] h-[68px] rounded-[10px] text-[18px] leading-[24px] shadow-none ${
                    !login || !password
                      ? "bg-[#CECECE] text-[#FFFFFF] cursor-not-allowed"
                      : "bg-[#7700FF] text-[#FFFFFF]"
                  }`}
                >
                  Войти
                </Button>
              </div>
              <div className="flex flex-col items-center justify-center">
                <Button
                  variant="outline"
                  className="w-[365px] h-[68px] rounded-[10px] text-[18px] leading-[24px] text-[#7700FF] border-none bg-[#F7F0FF] shadow-none"
                >
                  Зарегистрироваться
                </Button>
              </div>
              <p className="text-[18px] leading-[24px] text-[#9699A3] text-center">
                <span className="hover:underline cursor-pointer">
                  Забыли пароль?
                </span>
              </p>
            </div>
          </div>

          <div className="w-[403px] h-[123px] bg-white rounded-[15px] overflow-hidden max-w-md p-8 relative">
            <p className="absolute top-[10px] left-[149px] w-[105px] h-[24px] text-[18px] leading-[24px] text-[#9699A3]">
              Войти через
            </p>
            <div className="absolute top-[50px] left-[20px] flex items-center justify-center gap-[17px] w-[365px]">
              <Button
                className="w-[174px] h-[50px] px-[56px] py-[5px] rounded-[10px] text-[18px] flex items-center justify-center hover:opacity-90 bg-[#FFF1EC] text-[#FF4F12] shadow-none"
              >
                Ростелеком ID
              </Button>

              <Button
                className="w-[174px] h-[50px] px-[56px] py-[5px] rounded-[10px] text-[18px] flex items-center justify-center hover:opacity-90 bg-[#FFF1EC] text-[#FF4F12] shadow-none"
              >
                Код доступа
              </Button>
            </div>
          </div>
        </div>
        <Footer/>
      </main>
    </div>
  );
};

export default AuthPage;
