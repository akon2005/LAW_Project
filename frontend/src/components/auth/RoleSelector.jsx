/**
 * "Sign in as" selector.
 *
 * A restrained segmented control rather than an account-type card grid: it
 * sets the working context for the session and should not compete with the
 * form. Implemented as a radiogroup so arrow keys work the way they do in a
 * native radio list.
 */
import { useRef } from 'react'
import { ROLES } from '../../services/authService.js'

export default function RoleSelector({ value, onChange, disabled = false }) {
  const optionRefs = useRef([])

  const move = (currentIndex, delta) => {
    const count = ROLES.length
    const nextIndex = (currentIndex + delta + count) % count
    onChange(ROLES[nextIndex].id)
    optionRefs.current[nextIndex]?.focus()
  }

  const handleKeyDown = (event, index) => {
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        event.preventDefault()
        move(index, 1)
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault()
        move(index, -1)
        break
      case 'Home':
        event.preventDefault()
        onChange(ROLES[0].id)
        optionRefs.current[0]?.focus()
        break
      case 'End':
        event.preventDefault()
        const last = ROLES.length - 1
        onChange(ROLES[last].id)
        optionRefs.current[last]?.focus()
        break
      default:
        break
    }
  }

  return (
    <div className={`login-role${disabled ? ' is-disabled' : ''}`}>
      <span className="login-role__label" id="login-role-label">
        Sign in as
      </span>
      <div className="login-role__options" role="radiogroup" aria-labelledby="login-role-label">
        {ROLES.map((role, index) => {
          const selected = role.id === value
          return (
            <button
              key={role.id}
              ref={(node) => {
                optionRefs.current[index] = node
              }}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected ? 0 : -1}
              disabled={disabled}
              className={`login-role__option${selected ? ' is-selected' : ''}`}
              onClick={() => onChange(role.id)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              title={role.description}
            >
              {role.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
