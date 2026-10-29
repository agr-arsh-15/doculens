import * as Dialog from '@radix-ui/react-dialog'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import clsx from 'clsx'
import { AlertTriangle, Info, Loader2, X } from 'lucide-react'
import { forwardRef } from 'react'
import { gradeTone, severityMeta, TONE } from '../../lib/format'

export const cx = clsx

const BUTTON_VARIANTS = {
  primary: 'bg-ink text-paper hover:bg-ink-2 shadow-card',
  secondary: 'bg-surface text-ink border border-line hover:border-line-strong hover:bg-surface-2',
  ghost: 'text-ink-2 hover:bg-sunken/60',
  danger: 'bg-critical-soft text-critical hover:brightness-95',
}

export const Button = forwardRef(function Button(
  { as: Component = 'button', variant = 'secondary', size = 'md', className, loading, icon: Icon, children, ...props },
  ref,
) {
  return (
    <Component
      ref={ref}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent cursor-pointer',
        size === 'sm' ? 'h-8 px-3 text-[13px]' : size === 'lg' ? 'h-12 px-6 text-[15px]' : 'h-10 px-4 text-sm',
        BUTTON_VARIANTS[variant],
        className,
      )}
      disabled={Component === 'button' ? loading || props.disabled : undefined}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : Icon ? <Icon className="size-4" /> : null}
      {children}
    </Component>
  )
})

export function Card({ className, children, ...props }) {
  return (
    <div className={cx('rounded-2xl border border-line bg-surface shadow-card', className)} {...props}>
      {children}
    </div>
  )
}

export function Chip({ className, children, tone, solid, icon: Icon, ...props }) {
  const t = tone ? TONE[tone] : null
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        solid ? 'bg-ink text-paper' : t ? `${t.soft} ${t.text}` : 'bg-sunken/70 text-ink-2',
        className,
      )}
      {...props}
    >
      {Icon && <Icon className="size-3.5" />}
      {children}
    </span>
  )
}

export function SeverityBadge({ finding, className }) {
  const meta = severityMeta(finding)
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide', meta.soft, meta.text, className)}>
      <span className={cx('size-1.5 rounded-full', meta.bg)} />
      {meta.label}
    </span>
  )
}

export function GradeSeal({ grade, score, size = 'lg' }) {
  const tone = TONE[gradeTone(grade)]
  const big = size === 'lg'
  return (
    <div className="relative grid place-items-center" style={{ width: big ? 112 : 56, height: big ? 112 : 56 }}>
      <svg viewBox="0 0 100 100" className="absolute inset-0 -rotate-90">
        <circle cx="50" cy="50" r="44" fill="none" stroke="var(--line)" strokeWidth={big ? 6 : 8} />
        <circle
          cx="50" cy="50" r="44" fill="none" stroke={tone.color} strokeWidth={big ? 6 : 8} strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 276.5} 276.5`}
        />
      </svg>
      <div className="text-center leading-none">
        <div className={cx('font-serif font-bold', tone.text, big ? 'text-5xl' : 'text-2xl')}>{grade}</div>
        {big && <div className="mt-1 font-mono text-xs text-muted">{score}/100</div>}
      </div>
    </div>
  )
}

export function Spinner({ className }) {
  return <Loader2 className={cx('size-5 animate-spin text-muted', className)} />
}

export function Callout({ tone = 'info', title, children, className, action }) {
  const styles = {
    info: 'bg-accent-soft/70 border-accent/20 text-ink-2',
    warning: 'bg-caution-soft border-caution/30 text-ink-2',
    error: 'bg-critical-soft border-critical/30 text-ink-2',
  }
  const Icon = tone === 'info' ? Info : AlertTriangle
  return (
    <div className={cx('flex items-start gap-3 rounded-xl border px-4 py-3 text-sm', styles[tone], className)}>
      <Icon className={cx('mt-0.5 size-4 shrink-0', tone === 'error' ? 'text-critical' : tone === 'warning' ? 'text-caution' : 'text-accent')} />
      <div className="min-w-0 flex-1">
        {title && <div className="font-semibold text-ink">{title}</div>}
        <div className={title ? 'mt-0.5' : ''}>{children}</div>
      </div>
      {action}
    </div>
  )
}

export function Tooltip({ content, children, side = 'top' }) {
  if (!content) return children
  return (
    <TooltipPrimitive.Root delayDuration={200}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-xs rounded-lg bg-ink px-3 py-2 text-xs leading-relaxed text-paper shadow-card"
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-ink" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}

export const TooltipProvider = TooltipPrimitive.Provider

export function Switch({ checked, onCheckedChange, disabled, id }) {
  return (
    <SwitchPrimitive.Root
      id={id}
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className="relative h-6 w-11 shrink-0 cursor-pointer rounded-full bg-line-strong transition-colors data-[state=checked]:bg-ink disabled:cursor-not-allowed disabled:opacity-50"
    >
      <SwitchPrimitive.Thumb className="block size-5 translate-x-0.5 rounded-full bg-surface shadow transition-transform data-[state=checked]:translate-x-[22px]" />
    </SwitchPrimitive.Root>
  )
}

export function Tabs({ value, onValueChange, tabs, className, listClassName }) {
  return (
    <TabsPrimitive.Root value={value} onValueChange={onValueChange} className={className}>
      <TabsPrimitive.List className={cx('flex gap-1 rounded-xl bg-sunken/70 p-1', listClassName)}>
        {tabs.map((t) => (
          <TabsPrimitive.Trigger
            key={t.value}
            value={t.value}
            className="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium text-muted transition-colors hover:text-ink data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-card"
          >
            {t.label}
            {t.count !== undefined && (
              <span className={cx('rounded-full px-1.5 text-[11px] font-semibold', t.countClass || 'bg-line text-ink-2')}>{t.count}</span>
            )}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
    </TabsPrimitive.Root>
  )
}

export function Drawer({ open, onOpenChange, title, description, children, width = 'max-w-xl' }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/25 backdrop-blur-[2px] data-[state=open]:animate-in" />
        <Dialog.Content
          className={cx('fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-line bg-surface shadow-2xl outline-none', width)}
        >
          <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
            <div>
              <Dialog.Title className="font-serif text-xl font-semibold">{title}</Dialog.Title>
              {description ? (
                <Dialog.Description className="mt-0.5 text-sm text-muted">{description}</Dialog.Description>
              ) : (
                <Dialog.Description className="sr-only">{title}</Dialog.Description>
              )}
            </div>
            <Dialog.Close className="rounded-lg p-1.5 text-muted hover:bg-sunken hover:text-ink" aria-label="Close">
              <X className="size-5" />
            </Dialog.Close>
          </div>
          <div className="scrollbar-thin flex-1 overflow-y-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {Icon && (
        <div className="mb-3 grid size-12 place-items-center rounded-2xl bg-sunken text-muted">
          <Icon className="size-6" />
        </div>
      )}
      <div className="font-serif text-lg font-semibold">{title}</div>
      {children && <div className="mt-1 max-w-sm text-sm text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Select({ value, onChange, options, className, ...props }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cx(
        'h-10 cursor-pointer rounded-lg border border-line bg-surface px-3 pr-8 text-sm text-ink outline-none hover:border-line-strong focus:border-accent',
        className,
      )}
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export function Meter({ value, max = 100, tone = 'ok', className }) {
  return (
    <div className={cx('h-1.5 w-full overflow-hidden rounded-full bg-line', className)}>
      <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.max(2, (value / max) * 100)}%`, background: TONE[tone].color }} />
    </div>
  )
}
