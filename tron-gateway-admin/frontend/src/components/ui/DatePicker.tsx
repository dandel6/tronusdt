'use client';

import React, { forwardRef } from 'react';
import DatePicker, { registerLocale } from 'react-datepicker';
import { ko } from 'date-fns/locale';
import { Calendar } from 'lucide-react';
import 'react-datepicker/dist/react-datepicker.css';

// Register Korean locale
registerLocale('ko', ko);

interface DateRangePickerProps {
    startDate: Date | null;
    endDate: Date | null;
    onStartDateChange: (date: Date | null) => void;
    onEndDateChange: (date: Date | null) => void;
    className?: string;
}

// Custom input component for styled date picker
const CustomInput = forwardRef<HTMLButtonElement, { value?: string; onClick?: () => void }>(
    ({ value, onClick }, ref) => (
        <button
            type="button"
            onClick={onClick}
            ref={ref}
            className="h-10 px-4 bg-dark-900/50 border border-white/5 rounded-xl text-white hover:border-accent-primary/50 transition-colors flex items-center gap-2 min-w-[140px]"
        >
            <Calendar className="w-4 h-4 text-dark-400" />
            <span className={value ? 'text-white' : 'text-dark-500'}>
                {value || '날짜 선택'}
            </span>
        </button>
    )
);
CustomInput.displayName = 'CustomInput';

export function DateRangePicker({
    startDate,
    endDate,
    onStartDateChange,
    onEndDateChange,
    className = ''
}: DateRangePickerProps) {
    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <DatePicker
                selected={startDate}
                onChange={onStartDateChange}
                selectsStart
                startDate={startDate}
                endDate={endDate}
                locale="ko"
                dateFormat="yyyy-MM-dd"
                placeholderText="시작일"
                customInput={<CustomInput />}
                popperClassName="date-picker-popper"
                calendarClassName="date-picker-calendar"
                showPopperArrow={false}
                maxDate={new Date()}
            />
            <span className="text-dark-400">~</span>
            <DatePicker
                selected={endDate}
                onChange={onEndDateChange}
                selectsEnd
                startDate={startDate}
                endDate={endDate}
                minDate={startDate}
                locale="ko"
                dateFormat="yyyy-MM-dd"
                placeholderText="종료일"
                customInput={<CustomInput />}
                popperClassName="date-picker-popper"
                calendarClassName="date-picker-calendar"
                showPopperArrow={false}
                maxDate={new Date()}
            />
        </div>
    );
}

// Single date picker component
interface SingleDatePickerProps {
    date: Date | null;
    onChange: (date: Date | null) => void;
    placeholder?: string;
    maxDate?: Date;
    minDate?: Date;
    className?: string;
}

export function SingleDatePicker({
    date,
    onChange,
    placeholder = '날짜 선택',
    maxDate,
    minDate,
    className = ''
}: SingleDatePickerProps) {
    return (
        <DatePicker
            selected={date}
            onChange={onChange}
            locale="ko"
            dateFormat="yyyy-MM-dd"
            placeholderText={placeholder}
            customInput={<CustomInput />}
            popperClassName="date-picker-popper"
            calendarClassName="date-picker-calendar"
            showPopperArrow={false}
            maxDate={maxDate}
            minDate={minDate}
            className={className}
        />
    );
}
