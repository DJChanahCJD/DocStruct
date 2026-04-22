import { useState, useEffect } from "react";
import { FileText, Plug, Blocks, FlaskConical, BookOpen, Bug, HelpCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const DOC_TYPE_OPTIONS = [
  {
    value: "srs",
    label: "SRS 需求文档",
    icon: FileText,
    desc: "软件需求规格说明书",
    color: "bg-blue-50 border-blue-200 hover:border-blue-400",
    iconColor: "text-blue-500",
  },
  {
    value: "api",
    label: "API 文档",
    icon: Plug,
    desc: "接口定义与方法说明",
    color: "bg-green-50 border-green-200 hover:border-green-400",
    iconColor: "text-green-500",
  },
  {
    value: "design",
    label: "设计文档",
    icon: Blocks,
    desc: "系统架构与模块设计",
    color: "bg-purple-50 border-purple-200 hover:border-purple-400",
    iconColor: "text-purple-500",
  },
  {
    value: "test",
    label: "测试文档",
    icon: FlaskConical,
    desc: "测试用例与测试报告",
    color: "bg-orange-50 border-orange-200 hover:border-orange-400",
    iconColor: "text-orange-500",
  },
  {
    value: "manual",
    label: "用户手册",
    icon: BookOpen,
    desc: "使用说明与操作指南",
    color: "bg-teal-50 border-teal-200 hover:border-teal-400",
    iconColor: "text-teal-500",
  },
  {
    value: "issue",
    label: "问题单",
    icon: Bug,
    desc: "Bug 报告与缺陷跟踪",
    color: "bg-red-50 border-red-200 hover:border-red-400",
    iconColor: "text-red-500",
  },
  {
    value: "unknown",
    label: "未知类型",
    icon: HelpCircle,
    desc: "自动识别文档类型",
    color: "bg-gray-50 border-gray-200 hover:border-gray-400",
    iconColor: "text-gray-500",
  },
] as const;

interface DocTypeSelectorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (docType: string) => void;
  fileName?: string;
}

export function DocTypeSelectorDialog({
  open,
  onOpenChange,
  onConfirm,
  fileName,
}: DocTypeSelectorDialogProps) {
  const [selectedType, setSelectedType] = useState<string | null>(null);

  // Reset selection when dialog opens
  useEffect(() => {
    if (open) {
      setSelectedType(null);
    }
  }, [open]);

  const handleConfirm = () => {
    if (selectedType) {
      onConfirm(selectedType);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="text-lg">选择文档类型</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            {fileName ? (
              <span className="flex items-center gap-1">
                为文件 <span className="font-medium text-foreground">{fileName}</span> 选择类型
              </span>
            ) : (
              "请选择要上传的文档类型"
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-3 gap-3 py-4">
          {DOC_TYPE_OPTIONS.map((option) => {
            const Icon = option.icon;
            const isSelected = selectedType === option.value;

            return (
              <button
                key={option.value}
                onClick={() => setSelectedType(option.value)}
                className={cn(
                  "flex flex-col items-center justify-center rounded-lg border-2 p-3 transition-all duration-200",
                  "hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                  option.color,
                  isSelected
                    ? "border-primary ring-2 ring-primary ring-offset-2 shadow-md"
                    : "border-opacity-50"
                )}
              >
                <Icon className={cn("h-6 w-6 mb-2", option.iconColor)} />
                <span className="text-xs font-medium text-foreground">
                  {option.label}
                </span>
                <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">
                  {option.desc}
                </span>
              </button>
            );
          })}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} size="sm">
            取消
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!selectedType}
            size="sm"
            className="min-w-[80px]"
          >
            确认上传
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
