// @flow
/* global $:false */
import React from "react"

import CourseProductDetailEnroll from "../components/CourseProductDetailEnroll"
import ProgramProductDetailEnroll from "../components/ProgramProductDetailEnroll"

const expandExpandBlock = (event: MouseEvent) => {
  event.preventDefault()
  const blockTarget = event.target
  if (blockTarget instanceof HTMLElement) {
    const block = blockTarget.getAttribute("data-expand-body")
    if (block) {
      const elem = document.querySelector(`div#exp${block}`)
      elem && elem.classList && elem.classList.toggle("open")
      if (elem && elem.classList && elem.classList.contains("open")) {
        event.srcElement.innerText = "Show Less"
        elem.classList.remove("hide")
      } else {
        event.srcElement.classList.remove("fade")
        setTimeout(() => {
          requestAnimationFrame(() => {
            event.srcElement.innerText = "Show More"
            event.srcElement.classList.add("fade")
            elem && elem.classList && elem.classList.add("hide")
          })
        }, 225) // timeout
      }
    }
  }
}

const closeInstructorModal = (event: MouseEvent | KeyboardEvent) => {
  event.preventDefault()
  event.stopImmediatePropagation()

  const target = event.target

  if (target instanceof HTMLElement) {
    const instructorId: string =
      target.getAttribute("data-close-instructor-id") || ""

    if (
      instructorId &&
      ((event.keyCode && event.keyCode === 13) || event.type === "click")
    ) {
      const modal = document.getElementById(`instructor-modal-${instructorId}`)
      if (modal) {
        // $FlowFixMe
        $(modal)
          .off("hidden.bs.modal")
          .on("hidden.bs.modal", () => {
            const instructorImg = document.querySelector(
              `li.member-card-container img[data-instructor-id='${instructorId}']`
            )

            if (instructorImg) instructorImg.focus()
          })

        // $FlowFixMe
        $(modal).modal("hide")
      }
    }
  }
}

const openInstructorModal = (event: MouseEvent | KeyboardEvent) => {
  event.preventDefault()
  event.stopImmediatePropagation()

  const target = event.target

  if (target instanceof HTMLElement) {
    const instructorId: string = target.getAttribute("data-instructor-id") || ""

    if (
      instructorId &&
      ((event.keyCode && event.keyCode === 13) || event.type === "click")
    ) {
      const modal = document.getElementById(`instructor-modal-${instructorId}`)
      if (modal) {
        // $FlowFixMe
        $(modal).modal("show")

        document
          .querySelectorAll(`div#instructor-modal-${instructorId} button.close`)
          .forEach(button => {
            button.removeEventListener("keyup", closeInstructorModal)
            button.addEventListener("keyup", closeInstructorModal)
            button.removeEventListener("click", closeInstructorModal)
            button.addEventListener("click", closeInstructorModal)
          })
      }
    }
  }
}

type Props = {
  courseId: ?string,
  programId: ?string,
  userId: ?number
}

export class ProductDetailEnrollApp extends React.Component<Props> {
  render() {
    const { courseId, programId } = this.props

    document.querySelectorAll("a.expand_here_link").forEach(link => {
      link.removeEventListener("click", expandExpandBlock)
      link.addEventListener("click", expandExpandBlock)
    })

    document.querySelectorAll(".instructor-name").forEach(link => {
      link.removeEventListener("click", openInstructorModal)
      link.addEventListener("click", openInstructorModal)
      link.removeEventListener("keyup", openInstructorModal)
      link.addEventListener("keyup", openInstructorModal)
    })

    return programId ? (
      <ProgramProductDetailEnroll
        programId={programId}
      ></ProgramProductDetailEnroll>
    ) : (
      <CourseProductDetailEnroll
        courseId={courseId}
      ></CourseProductDetailEnroll>
    )
  }
}

export default ProductDetailEnrollApp
