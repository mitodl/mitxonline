import React, { useEffect, useState } from "react"
import { notNil } from "../lib/util"

type LoaderProps = {
  isLoading: boolean
  delayMs?: number
  children: React.ReactNode
}
const defaultLoaderDelayMs = 200

export default function Loader({ isLoading, delayMs, children }: LoaderProps) {
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
  }, [setLoaderVisible])

  if (!isLoading) {
    return <>{children}</>
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
