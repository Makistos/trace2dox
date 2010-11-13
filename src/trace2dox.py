#!/usr/bin/python
'''
Created on Nov 9, 2010

@author: mep
'''
import logging
import sys
import re
import string
import getopt
import operator

# Edit this template if you want different colours etc.
"""The template for the output file."""
mscTemplate = string.Template("""
/**
@msc
\thscale = "2";
    
\t${entities}
    
\t${messages}
@endmsc
*/
""")

""" Log file."""
LOG_FILENAME= 'trace2dox.log'
""" Default input file name."""
DEFAULT_INPUT_FILE = 'trace.log'
""" Default output file name."""
DEFAULT_OUTPUT_FILE = 'trace.msc'
""" Default namespace."""
NAMESPACE_STR = 'MAISA_'

""" Different message types supported by mscgen. """
MESSAGE_TYPES = '->|=>|=>>|>>|:>|<-|<=|<<=|<<|<:'

MESSAGE_PAT = '(\w+)(' + MESSAGE_TYPES + ')(\w+)(.+)*'

""" Default logic to use when filters have been defined. """
DEFAULT_LOGIC = 'AND'

""" Default configuration file (can be overriden on the command line) """
DEFAULT_CONFIG_FILE = '.trace2dox'

""" Configuration settings."""
configuration = {}

def usage():
    """ Prints usage help for this script."""
    print 'Usage:'
    print '\t-h, --help\tThis help text.'
    print '\t-i, --input\tInput file to read from (default:' + DEFAULT_INPUT_FILE +').'
    print '\t-o, --output\tOutput file to write to (default:' + DEFAULT_OUTPUT_FILE + ').'
    print '\t-n, --namespace\tNamespace to be removed from the beginning of entity names.'
    print '\t-f, --filter\tMessage filter, entities must be listed in a comma-separated list,' 
    print '\t-l, --logic\tLogic to use with the filter list (a=sender, b=receiver):'
    print '\t\t\tAND - a and b must be in the list (DEFAULT when filter is defined),'
    print '\t\t\tOR - a or b must be in the list,'
    print '\t\t\tNOT - neither a or b can be in the list,'
    print '\t\t\tNAND - Opposite to AND (everything except messsages where a and b are both in the list),'
    print '\t\t\tXOR - Exclusive OR, either a or b must be in the list, but not both.'
    print'\nWithout any parameters every message is included with full entity names.\n'

def setEntityAttributes(entity):
    """ 
    Sets the attributes for an entity. 
    
    If no entity specific attributes are found, returns the entity unchanged.
    """
    retval = entity
    if str(entity) in configuration:
        retval = entity + ' [' + configuration[entity] + ' ]'
        
    return retval
        
def setMessageAttributes(message):
    """     
    Sets the attributes for a message. If the message has some text attached, use that as the label and print the rest as is.
    If no attached text is found, copy the attributes from the configuration.
    
    If no message specific attributes are found, returns the message unchanged.
    """
    retval = ''.join(message)
    
    msgSeqStr = ''.join(message[0:3]) # This will be e.g. "A->B"
    if message[3] != '':
        if configuration.get(msgSeqStr, None) != None:
            # This message has a default attribute set
            if re.search('label=', configuration[msgSeqStr]) != None:
                # This message has a default label, replace it
                retval = msgSeqStr + ' [ ' + re.sub(r'label=\w+', 'label="' + message[3] + '"', configuration[msgSeqStr]) + ' ]'
            else:
                # No default label, so just attach the label and the default attributes
                retval = msgSeqStr + ' [ label="' + message[3] + '", ' + configuration[msgSeqStr] + ' ]'
        else:
            # No default attribute set, so just add the label
            retval = msgSeqStr + ' [ label="' + message[3] + '" ]'
    elif msgSeqStr in configuration:
        # Else if there are configured attributes for this message, use them
        retval = msgSeqStr + ' [ ' + ''.join(configuration[msgSeqStr]) + ' ]' 

    return retval

def trace2list(messageStr):
    """ Converts a message string into a list converting empty parts to '' instead of None which the match() function returns."""
    def f(x):
        if x == None:
            return ''
        else:
            return x
    
    retval = map(f, re.match(MESSAGE_PAT, messageStr).groups())
    return retval

def listFilter(message):
    """ 
    This function filters the message list according to given filter list and selected logic.
    
    Function returns either True or False. The parameter should be of style a->b with the 
    message type (in this case ->) included in the MESSAGE_TYPES regular expression pattern.
    
    If no filter is defined, True is returned.
    """
    if not "filters" in configuration:
        # No filtering, select every message
        return True
    else:
        #fields = re.split(MESSAGE_PAT,message)
        a = message[0]
        b = message[2] 
        result = {
                  'AND' : a in configuration['filters'] and b in configuration['filters'],
                  'OR'  : a in configuration['filters'] or b in configuration['filters'],
                  'NOT' : a not in configuration['filters'] and b not in configuration['filters'],
                  'NAND': not (a in configuration['filters'] and b in configuration['filters']),
                  'XOR': (a in configuration['filters'] and b not in configuration['filters']) or (a not in configuration['filters'] and b in configuration['filters'])
        }
        return result.get(configuration['logic'], lambda: True)

def initConfiguration():
    """ Initialises the configuration settings with initial values. """
    global configuration
    configuration['infile'] = DEFAULT_INPUT_FILE
    configuration['outfile'] = DEFAULT_OUTPUT_FILE
    configuration['namespace'] = NAMESPACE_STR
    configuration['logic'] = DEFAULT_LOGIC
    configuration['config-file'] = DEFAULT_CONFIG_FILE
    
def readConfiguration(filename):
    """ Reads the configuration file given """
    retval = {}
    
    try:
        f = open(filename, 'r')
    except IOError:
        logging.error('Configuration file ' + filename + ' not found!')
        sys.exit(2)
      
    for line in f:
        if not line.startswith('#') and line.find(':') > 0:
            # Line doesn't start with # and has a semi-colon, so it's a conf line
            conf = line.split(':',1)
            if not conf[0] in retval:
                retval[conf[0]] = conf[1].strip()
            
    return retval

def selectUnique(seq):
    """ Returns a list of unique entities in the message list."""
    justEntities = []
    # First get just the entities 
    for msg in seq:
        justEntities.append(operator.itemgetter(0,2)(msg))
    # Then get the unique items
    keys = {}
    for e in [item for sublist in justEntities for item in sublist]:
        keys[e] = 1
    return keys.keys()

def main(argv):
    global configuration
    cmd_params = {}
    
    logging.basicConfig(filename=LOG_FILENAME,
                        format='%(asctime)s %(levelname)s %(message)s',
                        level=logging.DEBUG)

    # Default file names
    initConfiguration()
    
    # Read commmand line parameters (these can override configuration file settings)
    try:
        opts, args = getopt.getopt(argv, 'i:o:n:f:l:c:h', ['input=', 'output=', 'namespace=', 'filter=', 'logic=', 'config=', 'help'])
        
    except getopt.GetoptError:
        usage()
        sys.exit(2)
 
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(2)
        elif opt in ('-i', '--input'):
            cmd_params['infile'] = arg
        elif opt in ('-o', '--output'):
            cmd_params['outFile'] = arg
        elif opt in ("-n", "--namespace"):
            cmd_params['namespace'] = arg
        elif opt in ('-f', '--filter'):
            cmd_params['filters'] = {}
            for entity in arg.split(','):
                if entity.find('=') > 0:
                    print entity
                    key, value = entity.split(':',2)
                else:
                    key =  value = entity
                cmd_params['filters'][key] = value
        elif opt in ('-l', '--logic'):
            arg_upper = str(arg).upper()
            if arg_upper != 'AND' and arg_upper != 'OR' and arg_upper != 'NOT' and arg_upper != 'NAND' and arg_upper != 'XOR':
                usage()
                sys.exit(2) 
            cmd_params['logic'] = arg_upper
        elif opt in ('-c', '--config'):
            cmd_params['config-file'] = arg
        else:
            usage()
            sys.exit(2)

    # Read the configuration file
    # First make sure we use the correct config file (i.e. use the command-line one if there is one)    
    configuration.update(cmd_params)
    # Then read the configuration file
    configuration.update(readConfiguration(configuration['config-file']))
    # Rewrite command-line parameters to make them primary settings
    configuration.update(cmd_params)
    
    #print configuration
    #for key, value in configuration.iteritems():
    #    print key + ' = ' + str(value)
            
    # Read the log
    try:
        f = open(configuration['infile'], "r")
    except IOError:
        logging.error('Input file ' + configuration['infile'] + ' not found!')
        sys.exit(2)
        
    # Find the traces, the list will look like e.g. ['a->b', 'b->a']    
    test = re.compile(configuration['traceid'])
    # The following will also remove any excess stuff in front of the 
    # sequence ID such as timestamps etc that the logger might add.
    traces = map(lambda x: re.sub('.*' + configuration['traceid'], '', re.sub(configuration['namespace'], '', x)).strip(), filter(test.search, f.readlines()))
    
    f.close()

    # Select messages from and to entities user is interested in. 
    filteredList = filter(listFilter, map(trace2list, traces))    
    
    # Then find the entities by selecting every item in list item #0 and #2.
    entityStr = '\t' + ','.join(map(setEntityAttributes, selectUnique(filteredList))) + ';'

    # Create the message list, each a-> needs a tab before them and a semi-colon and new line at the end and also set possible message attributes.
    messages = ';\n\t'.join(map(setMessageAttributes, filteredList)) + ';\n'                           
       
    # Finally print the output
    try:
        f = open(configuration['outfile'], 'w')
    except IOError:
        logging.error('Failed to open ' + configuration['outfile'] + ' for writing! Exiting...')
        sys.exit(2)
    
    f.write(mscTemplate.safe_substitute(entities=entityStr, messages=messages))
    
    f.close()
    
if __name__ == '__main__':
    main(sys.argv[1:])    