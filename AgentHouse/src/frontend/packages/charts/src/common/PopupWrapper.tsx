import React, { useState, useRef, useEffect, ReactNode, ReactElement, MouseEvent } from "react";
import { createPortal } from "react-dom";

let activePopupId: string | null = null;

type PopupWrapperProps = {
  trigger: ReactNode;
  children: ReactNode | ((props: { close: () => void }) => ReactNode);
};

export const PopupWrapper: React.FC<PopupWrapperProps> = ({ trigger, children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const buttonRef = useRef<HTMLDivElement | null>(null);
  const popupRef = useRef<HTMLDivElement | null>(null);
  const popupId = useRef<string>(Math.random().toString(36).substr(2, 9));

  useEffect(() => {
    setMounted(true);

    const handleClickOutside = (e: MouseEvent | MouseEventInit | any) => {
      if (
        popupRef.current &&
        !popupRef.current.contains(e.target) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target)
      ) {
        setIsOpen(false);
        activePopupId = null;
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen) {
      activePopupId = popupId.current;
      requestAnimationFrame(updatePosition);
    }
  }, [isOpen]);

  const updatePosition = () => {
    const button = buttonRef.current;
    const popup = popupRef.current;
    if (!button || !popup) return;

    const spacing = 1.5;
    const buttonRect = button.getBoundingClientRect();

    // Temporarily show popup to measure dimensions
    popup.style.visibility = "hidden";
    popup.style.display = "block";
    const popupRect = popup.getBoundingClientRect();
    popup.style.visibility = "";
    popup.style.display = "";

    const fitsBottom = window.innerHeight - buttonRect.bottom >= popupRect.height + spacing;
    const fitsTop = buttonRect.top >= popupRect.height + spacing;

    const top = fitsBottom
      ? buttonRect.bottom + spacing
      : fitsTop
      ? buttonRect.top - popupRect.height - spacing
      : Math.max(spacing, window.innerHeight - popupRect.height - spacing);

    const buttonLeft = buttonRect.left;
    const buttonRight = buttonRect.right;
    const popupWidth = popupRect.width;

    popup.style.top = `${top + window.scrollY}px`;
    if (buttonLeft + popupWidth > window.innerWidth) {
      popup.style.right = `${window.innerWidth - buttonRight + window.scrollX}px`;
      popup.style.left = "auto";
    } else {
      popup.style.left = `${buttonLeft + window.scrollX}px`;
      popup.style.right = "auto";
    }
  };

  const handleToggle = (e: MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    const newState = !isOpen;
    setIsOpen(newState);
    activePopupId = newState ? popupId.current : null;
  };

  return (
    <>
      <div ref={buttonRef} onClick={handleToggle} className="inline-block">
        {trigger}
      </div>

      {mounted &&
        isOpen &&
        createPortal(
          <div
            ref={popupRef}
            style={{
              position: "absolute",
              zIndex: 50,
              opacity: 0,
              transition: "opacity 150ms ease, transform 150ms ease",
            }}
            className="animate-popup"
            onAnimationEnd={() => {
              if (popupRef.current) {
                popupRef.current.style.opacity = "1";
              }
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="rounded-md shadow-md bg-white">
              {typeof children === "function"
                ? children({ close: () => setIsOpen(false) })
                : React.Children.map(children, (child) =>
                    React.isValidElement(child) &&
                    typeof child.props === "object" &&
                    child.props !== null &&
                    "close" in child.props
                      ? React.cloneElement(child as ReactElement<any>, {
                          close: () => setIsOpen(false),
                        })
                      : child
                  )}
            </div>
          </div>,
          document.body
        )}
    </>
  );
};
