#!/usr/bin/env python
import rospy

from flexbe_core.core.preemptable_state import PreemptableState
from flexbe_core.core.operatable_state_machine import OperatableStateMachine

from flexbe_core.proxy import ProxyPublisher, ProxySubscriberCached
from flexbe_msgs.msg import Container, OutcomeRequest
from std_msgs.msg import UInt8, String

from flexbe_core.state_logger import StateLogger


@StateLogger.log_outcomes('flexbe.outcomes')
class OperatableState(PreemptableState):
    """
    A state that supports autonomy levels and silent mode.
    Also, it allows being tracked by a GUI or anything else
    as it reports each transition and its initial structure.
    An additional method is provided to report custom status messages to the widget.
    """
    
    def __init__(self, *args, **kwargs):
        super(OperatableState, self).__init__(*args, **kwargs)
        self.transitions = None
        self.autonomy = None
        
        self._mute = False  # is set to true when used in silent state machine (don't report transitions)
        self._last_requested_outcome = None
        
        self._outcome_topic = 'flexbe/mirror/outcome'
        self._request_topic = 'flexbe/outcome_request'
        self._debug_topic = 'flexbe/debug/current_state'
        self._pub = ProxyPublisher()
        
        self.__execute = self.execute
        self.execute = self._operatable_execute
        
        
    def _build_msg(self, prefix, msg):
        """
        Adds this state to the initial structure message.
        
        @type prefix: string
        @param prefix: A path consisting of the container hierarchy containing this state.
        
        @type msg: ContainerStructure
        @param msg: The message that will finally contain the structure message.
        """
        
        # set path
        name = prefix + self.name
        
        # no children
        children = None
        
        # set outcomes
        outcomes = self._outcome_list
        
        # set transitions and autonomy levels
        transitions = []
        autonomy = []
        for i in range(len(outcomes)):
            outcome = outcomes[i]
            if outcome == 'preempted':          # set preempt transition
                transitions.append('preempted')
                autonomy.append(-1)
            else:
                transitions.append(str(self.transitions[outcome]))
                autonomy.append(self.autonomy[outcome])
        
        # add to message
        msg.containers.append(Container(name, children, outcomes, transitions, autonomy))
        

    def _operatable_execute(self, *args, **kwargs):
        outcome = self.__execute(*args, **kwargs)
        
        if self._is_controlled:

            # reset previously requested outcome if applicable
            if self._last_requested_outcome is not None and outcome == OperatableState._loopback_name:
                self._pub.publish(self._request_topic, OutcomeRequest(outcome=255, target=self._parent._get_path() + "/" + self.name))
                self._last_requested_outcome = None

            # request outcome because autonomy level is too low
            if not self._force_transition and (outcome in self.autonomy and self.autonomy[outcome] >= OperatableStateMachine.autonomy_level or
                                               outcome != OperatableState._loopback_name and
                                               self._get_path() in rospy.get_param('/flexbe/breakpoints', [])):
                if outcome != self._last_requested_outcome:
                    self._pub.publish(self._request_topic, OutcomeRequest(outcome=self._outcome_list.index(outcome), target=self._parent._get_path() + "/" + self.name))
                    rospy.loginfo("<-- Want result: %s > %s", self.name, outcome)
                    StateLogger.log('flexbe.operator', self, type='request', request=outcome,
                                    autonomy=OperatableStateMachine.autonomy_level,
                                    required=self.autonomy[outcome])
                    self._last_requested_outcome = outcome
                outcome = OperatableState._loopback_name
            
            # autonomy level is high enough, report the executed transition
            elif outcome != OperatableState._loopback_name:
                rospy.loginfo("State result: %s > %s", self.name, outcome)
                self._pub.publish(self._outcome_topic, UInt8(self._outcome_list.index(outcome)))
                self._pub.publish(self._debug_topic, String("%s > %s" % (self._get_path(), outcome)))
                if self._force_transition:
                    StateLogger.log('flexbe.operator', self, type='forced', forced=outcome,
                                    requested=self._last_requested_outcome)
                self._last_requested_outcome = None

        self._force_transition = False
        
        return outcome

    def _notify_skipped(self):
        super(OperatableState, self)._notify_skipped()


    def _enable_ros_control(self):
        super(OperatableState, self)._enable_ros_control()
        self._pub.createPublisher(self._outcome_topic, UInt8)
        self._pub.createPublisher(self._debug_topic, String)
        self._pub.createPublisher(self._request_topic, OutcomeRequest)
    
    
    



















