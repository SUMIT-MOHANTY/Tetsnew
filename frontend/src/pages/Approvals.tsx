import React, { useState } from 'react'
import { DashboardLayout } from '../components/layout/DashboardLayout'
import { Card, CardHeader, CardContent } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { 
  CheckSquare, 
  Clock, 
  Shield, 
  Bot, 
  FileText, 
  AlertCircle,
  Bell,
  ChevronRight,
  UserCheck,
  BarChart3
} from 'lucide-react'

// Mock approval preview data for Wave 2 preview
interface MockApprovalPreview {
  id: string
  agentAction: string
  evidenceSnippet: string
  confidenceScore: number
  initiativeName: string
  submittedAt: string
}

const mockApprovalPreviews: MockApprovalPreview[] = [
  {
    id: 'apr-001',
    agentAction: 'Recommend milestone extension for "Customer Portal Modernization"',
    evidenceSnippet: 'Current velocity indicates 14-day delay based on sprint burndown analysis...',
    confidenceScore: 87,
    initiativeName: 'Customer Portal Modernization',
    submittedAt: '2024-06-15T09:30:00Z'
  },
  {
    id: 'apr-002',
    agentAction: 'Flag budget overrun risk in "Supply Chain Optimization"',
    evidenceSnippet: 'Expenditure tracking shows 68% budget consumed at 45% completion...',
    confidenceScore: 92,
    initiativeName: 'Supply Chain Optimization',
    submittedAt: '2024-06-14T16:45:00Z'
  },
  {
    id: 'apr-003',
    agentAction: 'Suggest resource reallocation for "AI Recommendation Engine"',
    evidenceSnippet: 'Team capacity analysis indicates bottleneck in ML model training phase...',
    confidenceScore: 78,
    initiativeName: 'AI-Powered Recommendation Engine',
    submittedAt: '2024-06-14T11:20:00Z'
  }
]

// Toast notification component
const Toast: React.FC<{ message: string; onClose: () => void }> = ({ message, onClose }) => {
  React.useEffect(() => {
    const timer = setTimeout(onClose, 3000)
    return () => clearTimeout(timer)
  }, [onClose])

  return (
    <div className="fixed bottom-4 right-4 z-50 animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div className="bg-slate-900 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3">
        <Bell className="w-5 h-5 text-dertour-secondary" />
        <span className="text-sm font-medium">{message}</span>
      </div>
    </div>
  )
}

// Confidence score badge component
const ConfidenceBadge: React.FC<{ score: number }> = ({ score }) => {
  let colorClass = 'bg-emerald-100 text-emerald-700'
  if (score < 70) colorClass = 'bg-amber-100 text-amber-700'
  if (score < 50) colorClass = 'bg-red-100 text-red-700'

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      <BarChart3 className="w-3 h-3 mr-1" />
      {score}% confidence
    </span>
  )
}

// Mock approval queue preview card
const ApprovalQueuePreview: React.FC = () => {
  return (
    <div className="space-y-3">
      {mockApprovalPreviews.map((item, index) => (
        <div 
          key={item.id}
          className="border border-slate-200 rounded-lg p-4 bg-white/50 hover:bg-white transition-colors"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-4 h-4 text-dertour-primary" />
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                  Agent Action
                </span>
              </div>
              <p className="text-sm font-medium text-slate-900 mb-2">
                {item.agentAction}
              </p>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <FileText className="w-3 h-3" />
                <span className="truncate">{item.evidenceSnippet}</span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <ConfidenceBadge score={item.confidenceScore} />
              <span className="text-xs text-slate-400">
                {new Date(item.submittedAt).toLocaleDateString()}
              </span>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs text-slate-500">{item.initiativeName}</span>
            <div className="flex gap-2">
              <button 
                disabled
                className="px-3 py-1 text-xs font-medium text-slate-400 bg-slate-100 rounded cursor-not-allowed"
              >
                Review
              </button>
              <ChevronRight className="w-4 h-4 text-slate-300" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// Feature highlight card
const FeatureHighlight: React.FC<{
  icon: React.ElementType
  title: string
  description: string
}> = ({ icon: Icon, title, description }) => (
  <div className="flex items-start gap-3 p-4 bg-slate-50 rounded-lg">
    <div className="flex-shrink-0 w-10 h-10 bg-white rounded-lg shadow-sm flex items-center justify-center">
      <Icon className="w-5 h-5 text-dertour-primary" />
    </div>
    <div>
      <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
      <p className="text-xs text-slate-500 mt-1">{description}</p>
    </div>
  </div>
)

const Approvals: React.FC = () => {
  const [showToast, setShowToast] = useState(false)

  const handleNotifyMe = () => {
    setShowToast(true)
  }

  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto">
        {/* Page Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-dertour-primary/10 rounded-lg flex items-center justify-center">
              <CheckSquare className="w-5 h-5 text-dertour-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Approvals</h1>
              <p className="text-sm text-slate-500">Human-in-the-Loop Workflow</p>
            </div>
          </div>
        </div>

        {/* Coming Soon Banner */}
        <div className="mb-8 bg-gradient-to-r from-dertour-primary/5 to-dertour-secondary/5 border border-dertour-primary/20 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-12 h-12 bg-white rounded-full shadow-sm flex items-center justify-center">
              <Clock className="w-6 h-6 text-dertour-primary" />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-slate-900 mb-1">
                Coming in Wave 2
              </h2>
              <p className="text-sm text-slate-600 mb-4">
                The Human-in-the-Loop approval workflow is currently under development. 
                This feature will enable AI agents to submit material actions for human review, 
                with full evidence transparency and confidence scoring.
              </p>
              <Button 
                variant="primary" 
                size="md"
                leftIcon={<Bell className="w-4 h-4" />}
                onClick={handleNotifyMe}
              >
                Notify me when available
              </Button>
            </div>
            <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400">
              <Shield className="w-4 h-4" />
              <span>RBAC Protected</span>
            </div>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column: Mock Queue Preview */}
          <Card variant="elevated">
            <CardHeader 
              title="Approval Queue Preview" 
              subtitle="Sample agent actions awaiting human review"
            />
            <CardContent>
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800">
                  This is a preview of the Wave 2 approval queue interface. 
                  Actions shown are simulated for demonstration purposes.
                </p>
              </div>
              <ApprovalQueuePreview />
            </CardContent>
          </Card>

          {/* Right Column: Feature Overview */}
          <div className="space-y-6">
            <Card>
              <CardHeader 
                title="How It Works" 
                subtitle="The Human-in-the-Loop approval process"
              />
              <CardContent>
                <div className="space-y-3">
                  <FeatureHighlight
                    icon={Bot}
                    title="Agent Action Submission"
                    description="AI agents identify material decisions and submit them with structured evidence and confidence scores."
                  />
                  <FeatureHighlight
                    icon={FileText}
                    title="Evidence Display"
                    description="Review comprehensive evidence including data snapshots, trend analysis, and supporting documentation."
                  />
                  <FeatureHighlight
                    icon={UserCheck}
                    title="Human Review & Decision"
                    description="Authorized users review evidence, add comments, and approve or reject actions with full audit trails."
                  />
                  <FeatureHighlight
                    icon={Shield}
                    title="Role-Based Access"
                    description="EXECUTIVE and PMO roles can review and decide on agent-submitted actions."
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader 
                title="Workflow States" 
                subtitle="Approval request lifecycle"
              />
              <CardContent>
                <div className="flex items-center justify-between text-xs">
                  {['PENDING', 'IN_REVIEW', 'APPROVED'].map((state, idx) => (
                    <React.Fragment key={state}>
                      <div className="flex flex-col items-center">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium ${
                          idx === 0 ? 'bg-dertour-primary text-white' :
                          idx === 1 ? 'bg-dertour-secondary text-white' :
                          'bg-emerald-500 text-white'
                        }`}>
                          {idx + 1}
                        </div>
                        <span className="mt-2 text-slate-600 font-medium">{state}</span>
                      </div>
                      {idx < 2 && (
                        <div className="flex-1 h-0.5 bg-slate-200 mx-2" />
                      )}
                    </React.Fragment>
                  ))}
                </div>
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <p className="text-xs text-slate-500">
                    Additional states: <span className="font-medium text-slate-700">REJECTED</span> and{' '}
                    <span className="font-medium text-slate-700">ESCALATED</span> for timeout handling.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Bottom Info Section */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-dertour-primary">3</div>
            <div className="text-xs text-slate-500 mt-1">Approval Levels</div>
          </div>
          <div className="bg-slate-50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-dertour-secondary">100%</div>
            <div className="text-xs text-slate-500 mt-1">Audit Trail Coverage</div>
          </div>
          <div className="bg-slate-50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-emerald-600">&lt;24h</div>
            <div className="text-xs text-slate-500 mt-1">Target Review Time</div>
          </div>
        </div>
      </div>

      {/* Toast Notification */}
      {showToast && (
        <Toast 
          message="You'll be notified when Wave 2 releases" 
          onClose={() => setShowToast(false)} 
        />
      )}
    </DashboardLayout>
  )
}

export default Approvals
