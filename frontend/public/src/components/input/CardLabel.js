// @flow
// Provides a standardized label component, mostly for the new card design.

import React from "react"

type CardLabelProps = {
  htmlFor: string,
  label: string,
  subLabel?: string,
  isRequired?: boolean,
  className?: string,
  id?: string,
  children?: React$Element<*>
}

const CardLabel = ({
  children,
  htmlFor,
  label,
  subLabel,
  isRequired,
  className,
  id
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
        <div id={`${htmlFor}-subtitle`} className="subtitle">
          {subLabel}
        </div>
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
    <label className={`${labelClass || "fw-bold"}`} htmlFor={htmlFor} id={id}>
      {interior}
    </label>
  )
}

export default CardLabel
