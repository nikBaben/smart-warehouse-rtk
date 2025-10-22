"use client";

import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { Button } from "../ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select"
import ChevronDown from '@atomaro/icons/24/navigation/ChevronDown';
import ArrowRight from '@atomaro/icons/24/navigation/ArrowRight';

type Column<T> = {
  header: string;
  accessor: keyof T | ((row: T) => React.ReactNode);
  className?: string;
  align?: "left" | "center" | "right";
};

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  rowsPerPage?: number;
}

export function DataTableHistory<T extends object>({
  data,
  columns,
  rowsPerPage: initialRowsPerPage = 20,
}: DataTableProps<T>) {
  const [selectedRows, setSelectedRows] = useState<number[]>([]);
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(initialRowsPerPage);

  const totalPages = Math.ceil(data.length / rowsPerPage);
  const paginatedData = data.slice(
    (page - 1) * rowsPerPage,
    page * rowsPerPage
  );

  const toggleRow = (rowIndex: number) => {
    setSelectedRows((prev) =>
      prev.includes(rowIndex)
        ? prev.filter((i) => i !== rowIndex)
        : [...prev, rowIndex]
    );
  };

  const toggleAll = () => {
    const allIndices = paginatedData.map(
      (_, i) => (page - 1) * rowsPerPage + i
    );
    const allSelected = allIndices.every((i) => selectedRows.includes(i));

    if (allSelected) {
      setSelectedRows((prev) => prev.filter((i) => !allIndices.includes(i)));
    } else {
      setSelectedRows((prev) => Array.from(new Set([...prev, ...allIndices])));
    }
  };

  return (
    <div className="h-full flex flex-col bg-white rounded-[15px] overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <Table className="w-full text-center border-separate  border-spacing-y-[5px]">
          <TableHeader className="text-[10px] sticky top-0 bg-white z-10 shadow-none [&>tr]:border-0 [border-spacing:0!important] [&_th]:py-0 [&_th]:px-0">
            <TableRow className="text-black ">
              {/*<TableHead className="w-[24px] text-center">
                <Checkbox
                  checked={paginatedData.every((_, i) =>
                    selectedRows.includes((page - 1) * rowsPerPage + i)
                  )}
                  onCheckedChange={toggleAll}
                />
              </TableHead>*/}
              {columns.map((col, index) => (
                <TableHead key={index} className={cn(
                          "text-center py-[5px] relative",
                          index == 0 && "text-left"
                        )}>
                  {col.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>

          <TableBody className="[&_tr]:h-[30px]">
            {paginatedData.map((item, i) => {
              const rowIndex = (page - 1) * rowsPerPage + i;
              const isSelected = selectedRows.includes(rowIndex);

              return (
                <TableRow
                  key={rowIndex}
                  className={cn(
                    "transition-colors duration-150",
                    "hover:bg-[#E8E9EA]", "bg-[#F2F3F4]",
                    isSelected && "bg-[#F7F0FF]",
                    isSelected && "hover:bg-[#efe3fc]", 
                  )}
                    onClick={(e) => {
                      if (!(e.target as HTMLElement).closest('input[type="checkbox"]')) {
                        toggleRow(rowIndex);
                      }
                    }}
                >
                  {/*<TableCell className="w-[24px] text-center rounded-l-[5px]">
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => toggleRow(rowIndex)}
                      className="h-[10px] w-[10px] border-[#5A606D] border-[0.5px] rounded-[2px] data-[state=checked]:text-[#5A606D] data-[state=checked]:leading-[3px] shadow-none"
                    />
                  </TableCell> */}

                  {columns.map((col, index) => {
                    const value =
                      typeof col.accessor === "function"
                        ? col.accessor(item)
                        : (item[col.accessor as keyof T] as React.ReactNode);

                    const isFirst = index === 0;
                    const isLast = index === columns.length - 1;

                    return (
                      <TableCell
                        key={index}
                        className={cn(
                          "text-center py-[5px]",
                          isLast && "rounded-r-[5px] text-right",
                          isFirst && "rounded-l-[5px] text-left"
                        )}
                      >
                        {isFirst ? (
                          <div className="flex items-center gap-2">
                            <Checkbox
                              checked={isSelected}
                              onCheckedChange={() => toggleRow(rowIndex)}
                              className="h-[10px] w-[10px] border-[#5A606D] border-[0.5px] rounded-[2px]"
                              onClick={(e) => {
                                if (!(e.target as HTMLElement).closest('input[type="checkbox"]')) {
                                  toggleRow(rowIndex);
                                }
                              }}
                            />
                            {value}
                          </div>
                        ) : (
                          value
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-center items-center text-[12px] h-[43px] gap-[15px]">
        <div className="flex items-center gap-[4px]">
          {[...Array(totalPages)].map((_, i) => (
            <Button
              key={i}
              onClick={() => setPage(i + 1)}
              className={cn(
                "w-[18px] h-[18px] !p-0 !m-0 min-w-[18px] min-h-[18px] rounded-[5px] flex items-center justify-center text-[12px] font-light shadow-none",
                page === i + 1
                  ? "bg-[#F2F3F4] border-[#7700FF] border-[1px] text-black"
                  : "bg-[#F2F3F4] hover:bg-[#E8E9EA]"
              )}
            >
              {i + 1}
            </Button>
          ))}
          <Button
            onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            disabled={page === totalPages}
            className={cn(
              "bg-[#F2F3F4] w-[18px] h-[18px] !p-0 !m-0 min-w-[18px] min-h-[18px] rounded-[5px] flex items-center justify-center text-[12px] shadow-none",
              page === totalPages
                ? "opacity-50 cursor-not-allowed"
                : "hover:bg-[#F2F3F4]"
            )}
          >
            <ArrowRight fill="black" className="w-[8px] h-[8px]"/>
          </Button>
        </div>

        <div className="flex items-center gap-[10px]">
          <Select
            value={String(rowsPerPage)}
            onValueChange={(value) => {
              const newValue = Number(value);
              setRowsPerPage(newValue);
              setPage(1);
            }}
          >
            <SelectTrigger className="relative flex items-center justify-between w-auto !h-[18px] border-none rounded-[5px] bg-[#F2F3F4] text-[12px] pl-1 pr-1 focus:ring-0 focus:outline-none shadow-none font-light">
              <SelectValue className="truncate" />
            </SelectTrigger>

            <SelectContent
              align="end"
              sideOffset={4}
              className="min-w-[75px] rounded-[5px] border border-gray-200 bg-white shadow-none text-[12px]"
            >
              {[20, 50, 100].map((num) => (
                <SelectItem
                  key={num}
                  value={String(num)}
                  className={cn(
                    "px-2 py-[3px] rounded-[4px] text-gray-800 cursor-pointer h-[18px]",
                    "data-[highlighted]:bg-[#F2F3F4] data-[highlighted]:text-black transition-colors"
                  )}
                >
                  {num}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
