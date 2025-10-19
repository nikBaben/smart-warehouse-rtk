import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils"


type Column<T> = {
  header: string;
  accessor: keyof T | ((row: T) => React.ReactNode);
  className?: string;
  align?: "left" | "center" | "right";
};

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
}

export function DataTable<T extends object>({
  data,
  columns,
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-[5px] bg-[#FFFFFF] font-[400]">
      <div className="max-h-[288px] overflow-y-auto">
        <Table className="border-separate border-spacing-y-[5px] border-0 [&_*]:border-0 w-full !text-center">
          <TableHeader className="text-[10px]">
            <TableRow className="bg-[#FFFFFF] text-black">
              {columns.map((col, index) => (
                <TableHead key={index} className=" p-[0px]">
                  {col.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>

          <TableBody className="[&_tr]:h-[30px]">
              {data.map((item, i) => (
                  <TableRow key={i} className="bg-[#F6F7F7] row-height rounded-lg mb-2 text-[14px]">
                  {columns.map((col, index) => {
                      const value =
                      typeof col.accessor === "function"
                          ? col.accessor(item)
                          : (item[col.accessor as keyof T] as React.ReactNode); // приведение к ReactNode
                      const isFirst = index === 0;
                      const isLast = index === columns.length - 1;
                      return (
                      <TableCell
                          key={index}
                          className={cn(
                          "text-center py-[5px]",
                          isFirst && "rounded-l-lg",
                          isLast && "rounded-r-lg text-right"
                      )}
                      >
                          {value}
                      </TableCell>
                      );
                  })}
                  </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
