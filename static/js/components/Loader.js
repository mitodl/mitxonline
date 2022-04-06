// @flow
/* global SETTINGS:false */
import React, { useEffect, useState } from "react"

import { notNil } from "../lib/util"

type LoaderProps = {
  isLoading: boolean,
  delayMs?: number,
  children: React$Element<*> | Array<React$Element<*>>
}

const defaultLoaderDelayMs = 200

const Loader = (props: LoaderProps) => {
  const { isLoading, delayMs, children } = props
  const [loaderVisible, setLoaderVisible] = useState(false)

  useEffect(() => {
    if (!isLoading) return
    const timer = setTimeout(
      () => {
        setLoaderVisible(true)
      },
      notNil(delayMs) ? delayMs : defaultLoaderDelayMs
    )
    return () => clearTimeout(timer)
  }, [])

  if (!isLoading) {
    return children
  }
  return loaderVisible ? (
    <div className="text-center">
      <div className="lds-default">
        <div />
        <div />
        <div />
        <div />
        <div />
        <div />
        <div />
        <div />
        <div />
        <div />
        <div />
        <div />
      </div>
    </div>
  ) : null
}

export default Loader
