// @flow
// Provides a standardized label component, mostly for the new card design.

import React from "react"

type CardLabelProps = {
  htmlFor: string,
  label: string,
  subLabel?: string,
  isRequired?: boolean,
  className?: string,
  children?: React$Element<*>
}

const CardLabel = ({
  children,
  htmlFor,
  label,
  subLabel,
  isRequired,
  className
}: CardLabelProps) => {
  let labelClass = className || "fw-bold"
  let interior = <></>
  let required = <></>

  if (isRequired) {
    required = (
      <span className="required" aria-hidden="true">
        *
      </span>
    )
  }

  if (subLabel) {
    labelClass = "label-helptext"
    interior = (
      <>
        <div className={`${className || "fw-bold"}`}>
          {label}
          {required}
        </div>
        <div className="subtitle">{subLabel}</div>
        {children}
      </>
    )
  } else {
    interior = (
      <>
        {label}
        {required}
        {children}
      </>
    )
  }

  return (
    <label className={`${labelClass || "fw-bold"}`} htmlFor={htmlFor}>
      {interior}
    </label>
  )
}

export default CardLabel
