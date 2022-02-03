import React, { ChangeEventHandler, FocusEventHandler } from "react"
type RadioButtonProps = {
  field: {
    name: string
    value: string
    onChange: ChangeEventHandler
    onBlur: FocusEventHandler
  }
  id: string
  label: string
}
export const RadioButton = ({
  field: { name, value, onChange, onBlur },
  id,
  label,
  ...props
}: RadioButtonProps) => {
  return (
    <div>
      <input
        name={name}
        type="radio"
        id={id}
        value={id}
        checked={id === value}
        onChange={onChange}
        onBlur={onBlur}
        {...props}
      />
      <label htmlFor={id}>{label}</label>
    </div>
  )
}

type RadioButtonGroupProps = {
  className: string
  children: React.ReactChildren
}

export const RadioButtonGroup = ({
  className,
  children
}: RadioButtonGroupProps) => {
  return <div className={className}>{children}</div>
}
