// @flow
/* global SETTINGS:false */
import React from "react"

function InstituteLogo() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      aria-labelledby="instituteTitle instituteDesc"
      role="img"
      className="svg-site-logo"
    >
      <title id="instituteTitle">Institute Logo</title>
      <desc id="instituteDesc">MIT Logo</desc>
      <g strokeWidth="35" stroke="#A31F34">
        <path d="m17.5,0v166m57-166v113m57-113v166m57-166v33m58,20v113" />
        <path d="m188.5,53v113" stroke="#8A8B8C" />
        <path d="m229,16.5h92" strokeWidth="33" />
      </g>
    </svg>
  )
}

export default InstituteLogo
