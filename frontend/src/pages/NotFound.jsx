import { FileQuestion } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button, EmptyState } from '../components/ui'

export default function NotFound() {
  return (
    <EmptyState icon={FileQuestion} title="Page not found" action={<Button as={Link} to="/" variant="primary">Back to DocuLens</Button>}>
      The page you are looking for does not exist.
    </EmptyState>
  )
}
