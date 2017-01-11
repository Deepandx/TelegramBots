#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# ModismBot
# Created by Alexander Hirschfeld

import logging
import argparse
import time
import datetime


from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, RegexHandler, ConversationHandler


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global variables
authToken = None
mongoURI = None
mClient = None
mDatabase = None

# For the state machine of creating events, because conversation handlers are state machines
EVENTSELECT, EVENTTYPING, EVENTCREATE = range(100,103) 
POLLQUESTION, POLLANSWER, POLLGROUP = range(200,203)
USER_REG = 'user_reg'

# Utility commands
def checkTypeGroup(update):
    return (update.message.chat.type == 'group' or update.message.chat.type == 'supergroup')

def checkTypePrivate(update):
    return update.message.chat.type == 'private'

# Checks to see if a command is a valid command for the bot, aka @botname exists or doesn't
def checkValidCommand(text, username):
    text = text.split()[0]
    try:
        at = text.index('@')+1
        if text[at:] == username:
            return True
        return False
    except ValueError:
        return True


def createUserDict(from_user):
    userDict = dict()
    userDict['username'] = from_user.username
    userDict['name'] = from_user.first_name + " " + from_user.last_name
    userDict['_id'] = from_user.id
    userDict['chatID'] = from_user.id # Placeholder till they send /start to the bot


def createChatDoc(bot, update):
    if not checkValidCommand(update.message.text, bot.username):
        return

    logger.info("Creating Doc For :: Title: %s :: Username: %s :: ChatID: %s :: ChatType %s" % 
        (update.message.chat.title, update.message.from_user.username, update.message.chat.id, update.message.chat.type))
    reply_text = "Hello! Thanks for registering with @%s!\n" % bot.username
    # treating groups and super groups as the same entity, it makes things easier, and they basically are.
    if checkTypeGroup(update):
        findRes = mDatabase.groups.find({'_id':update.message.chat.id})
        keyboard = [[InlineKeyboardButton("Register with this chat by clicking this.", callback_data=USER_REG)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if findRes.count() == 0:
            reply_text += "Please type /help@%s to get a list of commands for this bot.\nPlease remember that most of the interaction with this bot will be through private messages." @ bot.username
            newGroup = dict()
            newGroup['_id'] = update.message.chat.id
            newGroup['title'] = update.message.chat.title
            newGroup['motd'] = "Here is the MOTD"
            newGroup['custom_commands'] = [{'command':'example','text':'This is a custom message, you can set a few of these'}]
            newGroup['activePolls'] = list()
            newGroup['food']
            newGroup['events'] = list()
            newGroup['users'] = [createUserDict(update.message.from_user)]
            mDatabase.groups.insert(newGroup) 
            logger.info("Group %s (%s) joined" % (update.message.chat.title, update.message.chat.id))
        elif findRes.count() > 1:
            # Find a good way to deal with this eventually
            logger.warn("There are two group entries for %s (%s). Please fix" % (update.message.chat.title, update.message.chat.id))
            reply_text="Something went wrong, please ask @YTKileroy about this and give him this number:%s" % update.message.chat.id
            reply_markup = None
        else:
            reply_text = 'Welcome back!'
            logger.info("Group %s (%s) joined again." % (update.message.chat.title, update.message.chat.id))
            newGroup = dict()
            newGroup['title'] = update.message.chat.title
            #newGroup['motd'] = "Here is the MOTD"
            #newGroup['custom_commands'] = [{'command':'example','text':'This is a custom message, you can set a few of these'}]
            newGroup['activePolls'] = list()
            newGroup['food']
            newGroup['events'] = list()
            #newGroup['users'] = [createUserDict(update.message.from_user)]
            mDatabase.groups.update({"_id":update.message.chat.id},{"$set":newGroup}) 

        update.message.reply_text(reply_text, reply_markup=reply_markup)

    elif checkTypePrivate(update):
        pass


## Commands for the user
def registerGroup(userID, groupID, groupTitle):
    createEventDoc

def start(bot, update):
    pass

def help(bot, update):
    pass



### Commands for creating an event.

def isTimeString(input):
    try:
        time.strptime(input, '%H:%M')
        return True
    except ValueError:
        return False

def isDateString(input):
    try:
        eventDate = time.strptime(input, '%m/%d/%Y')
        #print(eventDate)
        now = datetime.datetime.now()
        currDate = time.strptime('%d/%d/%d' %(now.month, now.day, now.year), '%m/%d/%Y')
        #print(currDate)
        return eventDate >= currDate
    except ValueError:
        #print('failure')
        return False

def createEventDoc(forChatTitle, user_data, username):
    result = mDatabase.groups.find({"title":forChatTitle})
    if result.count() == 1:
        logger.info("Creating Event for %s" % forChatTitle)
        newEvent = dict()
        newEvent['name'] = user_data['Name']
        newEvent['description'] = user_data['Description']
        newEvent['time'] = user_data['Time']
        newEvent['place'] = user_data['Place']
        newEvent['date'] = newEvent['Date']
        newEvent['creator'] = username
        mDatabase.groups.update({'title':forChatTitle},{'$push':{'events':newEvent}})
        logger.debug("Created Event: %s" % (str(newEvent)))
        return True
    else:
        return False

def eventStartEditing(bot, update, user_data):
    if checkTypePrivate(update):
        logger.info("%s (%s) is creating an event." % (update.message.from_user.username, update.message.from_user.id))

        #reset all keys, and set them.
        for key in ['Name','Time','Date','Description','Place','Group']:
            user_data[key] = None

        # Set up the keyboard
        reply_keyboard = [['Name', 'Time', 'Date'],
                          ['Group','Place'],
                          ['Description']]

        # If the user has answered all questions, add 'done', otherwise just add 'cancel'
        if all (key in user_data for key in ['Name','Time','Date','Description','Place','Group']):
            reply_keyboard.append(['Cancel','Done'])
        else:
            reply_keyboard.append(['Cancel'])

        # Make the markup, needs to be one time because users need to reply to this thing.
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        reply_text = "Please select which you would like to edit, once you've entered something for all of these, you will be able to create the event."

        update.message.reply_text(reply_text, reply_markup=markup)

        #We are prompting them to select an event, need to handle that next
        return EVENTSELECT
    else:
        update.message.reply_text("Please message this bot directly to create an event.")
        return ConversationHandler.END


def eventSelectEditing(bot, update, user_data):

    user_data[user_data['editing_choice']] = update.message.text
    reply_text = ""

    if user_data['editing_choice'] == 'Time' and not isTimeString(update.message.text):
        reply_text = "Your time string is not formatted correctly, please try again.\n\n"
        user_data['Time'] = None
    elif user_data['editing_choice'] == 'Date' and not isDateString(update.message.text):
        reply_text = 'You Date string is not formatted correctly (m/d/20xx), please try again.\n\n'
        user_data['Date'] = None

    reply_keyboard = [['Name', 'Time', 'Date'],
                          ['Group','Place'],
                          ['Description']]

    if all (key in user_data for key in ['Name','Time','Date','Description','Place','Group']):
        reply_keyboard.append(['Cancel','Done'])
    else:
        reply_keyboard.append(['Cancel'])
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    reply_text += "Please select which you would like to edit, once you've entered something for all of these, you will be able to create the event."
    update.message.reply_text(reply_text, reply_markup=markup)
    return EVENTSELECT

def eventPromptTyping(bot, update, user_data):
    # Which did they choose! Store it for later use
    userChoice = update.message.text
    user_data['editing_choice'] = userChoice

    # If they managed to select done
    if userChoice == 'Done':
        if createEventDoc(user_data['Group'], user_data, update.message.from_user.username):
            reply_text = "Created the event!"
            update.message.reply_text(reply_text)
            return ConversationHandler.END

    elif userChoice == 'Cancel':
        reply_text = "Canceled."
        for key in ['Name','Time','Date','Description','Place','Group','editing_choice']:
            user_data[key] = None
            update.message.reply_text(reply_text)
            return ConversationHandler.END

    elif userChoice == 'Time':
        reply_text = "Please send me the Time of the event in HH:MM format."

    elif userChoice == 'Date':
        reply_text = "Please send me the Date of this event in MM/DD/YY"
    else:
        reply_text = "Please send me the %s of the event." % userChoice.lower()
    update.message.reply_text(reply_text)

def eventCancel(bot, update, user_data):
    reply_text = "Canceled."
    for key in ['Name','Time','Date','Description','Place','Group','editing_choice']:
        user_data[key] = None
    update.message.reply_text(reply_text)
    return ConversationHandler.END




# Creating Polls!

def pollStartEditing(bot, update, user_data):
    if not checkTypePrivate(update):
        update.message.reply_text("Please send this bot a private message.")
        return ConversationHandler.END

    reply_text = "Please send me the Question.\n\n"
    reply_text += "Send /done when done and /cancel to cancel."

    msg = update.MessageHandler.reply_text(reply_text)

    user_data['Message'] = msg.message_id
    user_data['Question'] = ""
    user_data['Answers'] = list()

    return POLLQUESTION


def pollQuestionReceived(bot, update, user_data):
    user_data['Question'] = update.message.text
    reply_text = user_data['Question'] + '\n\n'
    reply_text += "Send me the answers.\n"
    reply_text += "Send /done when done and /cancel to cancel."

    bot.edit_text(chat_id=update.message.chat_id,
                 message_id = user_data['Message'],
                 text=reply_text)

    return POLLANSWER

def pollAnswersReceived(bot, update, user_data):
    user_data['Answers'].append(update.message.text)
    reply_text = user_data['Question'] + '\n\n'
    for text in user_data['Answers']:
        reply_text += text + '\n\n'

    reply_text += "Send me the answers.\n"
    reply_text += "Send /done when done and /cancel to cancel."

    bot.edit_text(chat_id=update.message.chat_id,
                 message_id = user_data['Message'],
                 text=reply_text)

    return POLLANSWER


def pollAskWhichGroup(bot, update, user_data):
    result = mDatabase.groups.find({'users':update.message.from_user.id})
    if result.count():
        for chat in 

def pollCreatePoll(bot, update, user_data):
    pass

def pollCancel(bot, update, user_data):
    pass
            

### Commands for Message of the day.    


# Message of the day
def MOTD(bot, update):
    logger.debug('MOTD called for %s (%s)' % (update.message.chat.title, update.message.chat.id))
    if not checkValidCommand(update.message.text, bot.username):
        return
    result = mDatabase.groups.find({'_id':update.message.chat_id})
    if not result.count():
        return
    update.message.reply_text(result.next()['motd'])

def setMOTD(bot, update):
    logger.debug('setMOTD called for %s (%s)' % (update.message.chat.title, update.message.chat.id))
    if not checkValidCommand(update.message.text, bot.update):
        return
    newMOTD = update.message.text[update.message.text.index(' ')+1:]
    logger.debug('setMOTD to: %s' % newMOTD)
    mDatabase.groups.update(
        {'_id':update.message.chat.id},
        {'motd':newMOTD},
        upsert=True)


### Callback Query Handler

def callbackHandler(bot, update, chat_data, user_data):
    query = update.callback_query
    data = query.data

    if data == USER_REG:
        chat_id = query.message.chat_id
        mDatabase.groups.update(
            {'_id':chat_id},
            {'$addToSet':{'users':createUserDict(query.from_user)}},
            upsert=True)

def handleStatusUpdates(bot, update):
    chat_id = update.message.chat_id
    if update.message.left_chat_member and not update.message.left_chat_member == bot.username:
        mDatabase.groups.update(
            {'_id':chat_id},
            {'$pull':{'users':{'_id':update.message.left_chat_member.id}}})

    elif update.message.left_chat_member:
        mDatabase.groups.remove({'_id':chat_id})
        logger.info("Removing %s (%s), bot was removed." % update.message.chat.title, update.message.chat.id)

    elif update.message.new_chat_member and not update.message.new_chat_member == bot.username:
        mDatabase.groups.update(
            {'_id':chat_id},
            {'$addToSet':{'users':createUserDict(update.message.new_chat_member)}})
    elif update.message.new_chat_member:
        createChatDoc(bot, update)


def main():
    global mClient, mDatabase

    mClient = MongoClient(mongoURI)
    mDatabase = mClient[mDatabase]

    try:
        serverInfo = mClient.server_info()
        logger.info("Mongo Connection Active")
        logger.debug("Connected to Mongo Server: %s." % serverInfo)
    except:
        logger.error("Could not connect to the Mongo Server.")
        raise

    updater = Updater(authToken)
    dp = updater.dispatcher

    #Commands
    
    dp.add_handler(CommandHandler('motd', MOTD))
    dp.add_handler(CommandHandler('setmotd', setMOTD))


    # Conversation Handlers

    # ['Name','Time','Date','Description','Place','Group', 'Cancel','Done']:
    createEvent = ConversationHandler(
         entry_points=[CommandHandler('createevent', eventStartEditing, pass_user_data=True)],
         states = {
            EVENTSELECT: [RegexHandler('^(Name|Time|Date|Description|Place|Group|Cancel|Done)$',
                                        eventPromptTyping,
                                        pass_user_data=True)],
            EVENTTYPING: [MessageHandler(Filters.text, 
                                        eventSelectEditing.
                                        pass_user_data=True)]
            },
         fallback=MessageHandler(Filters.all, eventCancel, pass_user_data=True) 
         )
    dp.add_handler(createEvent)

    createPoll = ConversationHandler(
        entry_points=[CommandHandler('createpoll', pollStartEditing, pass_user_data=True)],
        states = {
            POLLQUESTION: [MessageHandler(Filters.text,
                                          pollQuestionReceived,
                                          pass_user_data=True)],
            POLLANSWER: [MessageHandler(Filters.text,
                                        pollAnswersReceived,
                                        pass_user_data=True),
                        CommandHandler('done',
                                        pollAskWhichGroup,
                                        pass_user_data=True)],
            POLLGROUP: [MessageHandler(Filters.text,
                                        pollCreatePoll,
                                        pass_user_data=True)]},
    fallback=[MessageHandler('cancel',
                            pollCancel,
                            pass_user_data=True)])
    dp.add_handler(createPoll)

    #Callback
    dp.add_handler(CallbackQueryHandler(callbackHandler, pass_chat_data = True, pass_user_data = True))

    # Message
    dp.add_handler(MessageHandler(Filters.status_update, handleStatusUpdates))

    updater.start_polling()
    updater.idle()

def startFromCLI():
    global mDatabase, mongoURI, authToken
    # Specifying a lot of arguments, Don't want to have to deal with config files, maybe I will later for other things
    parser = argparse.ArgumentParser()
    parser.add_argument('auth', type=str, 
                        help="The Auth Token given by Telegram's @botfather")
    parser.add_argument('-muri','--mongoURI', default='mongodb://localhost:27017', 
                        help="The MongoDB URI for connection and auth")
    parser.add_argument('-mDB', '--mongoDB', default="ChatUtil",
                        help="The database for MongoDB, default is ChatUtil")
    parser.add_argument('-l','--llevel', default='debug', choices=['debug','info','warn','none'], 
                        help='Logging level for the logger, default = debug')

    # This is not somehting that needs to be added, but it is useful for some things I think.
    logLevel = {'none':logging.NOTSET,'debug':logging.DEBUG,'info':logging.INFO,'warn':logging.WARNING} 
    args = parser.parse_args()


    logger.setLevel(logLevel[args.llevel])

    mDatabase = args.mongoDB
    mongoURI = args.mongoURI
    logger.info("MongoDB URI: %s" % (mongoURI))
    logger.info("MongoDB DB: %s" % (mDatabase))
    authToken = args.auth
    logger.debug("TelegramAuth: %s" % (authToken))

if __name__ == '__main__':
    startFromCLI()
    main()

